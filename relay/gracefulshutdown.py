"""Graceful shutdown: hand off leadership before stopping, not after.

A broker that stops abruptly forces an election for every
partition it led, and elections take time during which those
partitions are unavailable, so an unplanned-looking outage
follows a perfectly planned restart. Graceful shutdown inverts
the order: before the broker stops, it moves leadership of each
partition it leads to an in-sync follower, so when it finally
exits, no partition needs an election because none of them are
led by the departing broker anymore. The handoff has a
precondition that cannot be skipped: leadership only moves to a
replica that is fully caught up, because handing leadership to a
lagging follower would truncate the records between its position
and the leader's, converting a graceful shutdown into data loss,
which is the worst possible outcome for the one operation whose
entire purpose is safety. A partition with no caught-up follower
cannot be handed off, and the broker reports it rather than
either stalling forever or exiting and forcing the election it
was trying to avoid, because the honest answer to "this partition
has nowhere safe to go" is to tell the operator, who can add a
replica or accept the brief election, not to pretend the problem
away. The report counts handed-off against stranded, since a
graceful shutdown that stranded half its partitions was not
graceful, it was optimistic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class ShutdownPlan:
    departing: str
    led_partitions: dict[int, list[str]]
    caught_up: dict[int, set[str]]
    handed_off: dict[int, str] = field(default_factory=dict)
    stranded: list[int] = field(default_factory=list)

    def execute(self) -> str:
        for partition, replicas in self.led_partitions.items():
            candidates = [
                r
                for r in replicas
                if r != self.departing
                and r in self.caught_up.get(partition, set())
            ]
            if candidates:
                self.handed_off[partition] = candidates[0]
            else:
                self.stranded.append(partition)
        return self.report()

    def may_exit(self) -> bool:
        return not self.stranded

    def report(self) -> str:
        total = len(self.led_partitions)
        lines = [
            f"{len(self.handed_off)} of {total} partition(s) "
            "handed off, no election needed for them"
        ]
        if self.stranded:
            lines.append(
                f"  {len(self.stranded)} stranded with no "
                "caught-up follower: told to the operator, not "
                "pretended away, because handing to a laggard "
                "would truncate committed records"
            )
        else:
            lines.append(
                "  every partition handed off; a clean exit with "
                "no partition left leaderless"
            )
        return "\n".join(lines)


def validate_handoff(
    partition: int,
    target: str,
    caught_up: set[str],
) -> None:
    if target not in caught_up:
        raise Invalid(
            f"partition {partition} cannot hand off to {target}; "
            "it is not caught up, and handing leadership to a "
            "laggard turns graceful shutdown into data loss"
        )
