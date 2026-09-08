"""Consumer groups: progress is a committed offset, not a feeling.

A group is a name that owns one committed offset per
partition, and everything about delivery semantics hides in
one ordering decision: commit before processing and a crash
loses the record in hand, at-most-once; process before
committing and a crash replays it, at-least-once. The group
tracker does not pretend to solve this, it makes the choice
explicit per group and reports which contract each group
signed, because the teams that get burned are the ones who
never knew they had chosen. Commits must move forward,
skipping records is legal but logged as a skip rather than
disguised as progress, and lag is computed against the
partition watermark, the only honest denominator, since lag
against the log's end counts records the consumer was never
allowed to read.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid, Missing
from relay.partition import Partition

CONTRACTS = ("at-least-once", "at-most-once")


@dataclass
class ConsumerGroup:
    name: str
    contract: str
    committed: dict[int, int] = field(default_factory=dict)
    skips_logged: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.contract not in CONTRACTS:
            raise Invalid(
                f"{self.name} must sign a delivery contract: "
                f"one of {CONTRACTS}; the teams that get "
                "burned never knew they had chosen"
            )

    def position(self, partition_number: int) -> int:
        return self.committed.get(partition_number, 0)

    def commit(
        self, partition: Partition, offset: int
    ) -> str:
        held = self.position(partition.number)
        if offset < held:
            raise Invalid(
                f"{self.name} committed {held} already; "
                "commits move forward"
            )
        if offset > partition.high_watermark:
            raise Invalid(
                "cannot commit past the watermark; that is "
                "claiming credit for records not yet promised"
            )
        jumped = offset - held
        if jumped > 1:
            skipped = jumped - 1
            self.skips_logged.append(
                f"partition {partition.number}: skipped "
                f"{skipped} record(s) between {held} and "
                f"{offset - 1}"
            )
        self.committed[partition.number] = offset
        note = (
            f"; {jumped - 1} skip(s) logged, not disguised "
            "as progress"
            if jumped > 1
            else ""
        )
        return (
            f"{self.name} committed partition "
            f"{partition.number} to {offset}{note}"
        )

    def lag(self, partition: Partition) -> int:
        return partition.lag_of(
            min(
                self.position(partition.number),
                partition.high_watermark,
            )
        )

    def contract_line(self) -> str:
        if self.contract == "at-least-once":
            return (
                f"{self.name}: process then commit; a crash "
                "replays the record in hand"
            )
        return (
            f"{self.name}: commit then process; a crash loses "
            "the record in hand"
        )


@dataclass
class GroupRegistry:
    groups: dict[str, ConsumerGroup] = field(
        default_factory=dict
    )

    def register(self, name: str, contract: str) -> ConsumerGroup:
        if name in self.groups:
            raise Invalid(f"group {name} already exists")
        group = ConsumerGroup(name=name, contract=contract)
        self.groups[name] = group
        return group

    def get(self, name: str) -> ConsumerGroup:
        group = self.groups.get(name)
        if group is None:
            raise Missing(f"group {name} does not exist")
        return group
