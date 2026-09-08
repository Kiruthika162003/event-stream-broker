"""Controlled shutdown: move leadership off a broker before it stops.

When a broker stops abruptly, every partition it led is suddenly
leaderless, and the cluster must detect the failure, then elect new
leaders, a window in which those partitions are unavailable and, if
the broker was the last in-sync replica for any of them, a window in
which an unclean election might lose records. Controlled shutdown
avoids that by moving leadership first, while the broker is still
healthy. Before the broker goes down it asks the controller to
transfer each of its partition leaderships to another in-sync replica,
one partition at a time, and only once every leadership has moved does
it actually stop. Because the handoffs happen while the old leader is
still up and fully caught up, the new leader takes over with every
committed record already present, so there is no unavailability gap
and no risk of loss. The catch is a partition for which the shutting-
down broker is the only in-sync replica: there is nowhere to move
leadership that would not be an unclean election, so controlled
shutdown cannot complete cleanly for that partition. The honest
behavior is to report it rather than pretend, so the operator can wait
for another replica to catch up, or accept the risk deliberately. The
coordinator plans a handoff for each led partition, choosing the
in-sync replica with the highest log end as the new leader, collects
the partitions that have no safe target, and refuses to declare the
shutdown clean while any remain. It reports the moves made and the
blocked partitions, because a controlled shutdown that quietly left
partitions stranded is the failure it was meant to prevent wearing the
costume of success."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class _Partition:
    name: str
    leader: str
    # in-sync replica -> log end offset (includes the current leader)
    in_sync: dict[str, int]


@dataclass
class ControlledShutdown:
    broker: str
    partitions: list[_Partition] = field(default_factory=list)

    def led_by_broker(self, name: str, in_sync: dict[str, int]) -> None:
        if self.broker not in in_sync:
            raise Invalid(
                f"'{self.broker}' is not in the in-sync set of '{name}'; it "
                "cannot be leading a partition it is not in sync for"
            )
        self.partitions.append(_Partition(name=name, leader=self.broker, in_sync=in_sync))

    def plan(self) -> dict[str, str]:
        # a handoff target is the highest-log-end in-sync replica that is not us
        moves: dict[str, str] = {}
        for p in self.partitions:
            targets = {r: e for r, e in p.in_sync.items() if r != self.broker}
            if targets:
                moves[p.name] = max(targets, key=lambda r: targets[r])
        return moves

    def blocked(self) -> list[str]:
        # partitions where we are the only in-sync replica have no safe target
        return [
            p.name
            for p in self.partitions
            if all(r == self.broker for r in p.in_sync)
        ]

    def is_clean(self) -> bool:
        return not self.blocked()

    def note(self) -> str:
        moves = self.plan()
        blocked = self.blocked()
        if blocked:
            return (
                f"{len(moves)} leadership move(s) planned, but {len(blocked)} "
                f"partition(s) blocked: {sorted(blocked)}; shutting down now "
                "would strand them, the failure controlled shutdown prevents"
            )
        return (
            f"{len(moves)} leadership move(s) planned, none blocked; every "
            "handoff goes to a caught-up replica, no gap and no loss"
        )
