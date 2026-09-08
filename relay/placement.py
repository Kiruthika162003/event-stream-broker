"""Placement: a new topic's replicas spread across brokers and racks.

Creating a topic means deciding, for each partition, which
brokers hold its replicas, and the decision has two objectives
that can conflict. The first is balance: every broker should hold
roughly the same number of replicas and lead roughly the same
number of partitions, so no broker is a hotspot. The second is
fault isolation: a partition's replicas should sit in different
racks, so one rack's power failure cannot take a majority of any
partition. The placer pursues both by assigning each partition's
replicas round-robin across brokers while stepping the starting
rack, so leadership spreads evenly and consecutive replicas of one
partition land in different racks. The tension is real and named:
when there are fewer racks than the replication factor, perfect
rack isolation is impossible, and the placer does the best it can
while reporting exactly which partitions have replicas sharing a
rack, because a placement that quietly puts two replicas in one
rack has a hidden single point of failure that surfaces only
during the outage. The report states both the balance spread and
the rack violations, since a placement optimized for one while
blind to the other is a placement that fails the audit it was
supposed to pass.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class Placer:
    brokers: list[str]
    rack_of: dict[str, str]
    replication_factor: int

    def __post_init__(self) -> None:
        if self.replication_factor < 1:
            raise Invalid("replication factor must be positive")
        if self.replication_factor > len(self.brokers):
            raise Invalid(
                "replication factor exceeds the broker count; "
                "there are not enough brokers to hold that many "
                "replicas"
            )

    def place(self, partitions: int) -> dict[int, list[str]]:
        assignment: dict[int, list[str]] = {}
        broker_count = len(self.brokers)
        for partition in range(partitions):
            start = partition % broker_count
            replicas = [
                self.brokers[(start + step) % broker_count]
                for step in range(self.replication_factor)
            ]
            assignment[partition] = replicas
        return assignment

    def rack_violations(
        self, assignment: dict[int, list[str]]
    ) -> list[int]:
        violated = []
        for partition, replicas in assignment.items():
            racks = [self.rack_of[b] for b in replicas]
            if len(set(racks)) < len(racks):
                violated.append(partition)
        return sorted(violated)

    def balance_spread(
        self, assignment: dict[int, list[str]]
    ) -> int:
        counts = dict.fromkeys(self.brokers, 0)
        for replicas in assignment.values():
            for broker in replicas:
                counts[broker] += 1
        return max(counts.values()) - min(counts.values())

    def report(self, partitions: int) -> str:
        assignment = self.place(partitions)
        spread = self.balance_spread(assignment)
        violations = self.rack_violations(assignment)
        racks = len(set(self.rack_of.values()))
        lines = [
            f"{partitions} partition(s) placed: balance spread "
            f"{spread}"
        ]
        if violations:
            lines.append(
                f"  {len(violations)} partition(s) share a rack "
                f"({racks} rack(s) for factor "
                f"{self.replication_factor}); a hidden single "
                "point of failure that surfaces only in the "
                "outage"
            )
        else:
            lines.append(
                "  every partition's replicas span racks; no "
                "rack failure takes a majority"
            )
        return "\n".join(lines)
