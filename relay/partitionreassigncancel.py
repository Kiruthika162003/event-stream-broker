"""Reassignment cancel: revert to the original replicas, drop the half-copied ones.

A partition reassignment can be slow, copying a large log to new
brokers, and an operator sometimes needs to cancel one mid-flight,
because it is saturating the network or was started by mistake or the
target broker turned out to be the wrong choice. Cancelling is not just
forgetting the plan; it has to leave the partition in a clean, defined
state. A reassignment has an original replica set and a target set, and
while it runs the partition's replicas are the union of the two, the
originals still serving and the targets catching up. To cancel, the
partition reverts to exactly its original replica set: the target
replicas that were only there for the move are dropped, including any
partial log they had copied, and leadership, if it had moved to a new
replica, moves back to an original. The one case that cannot revert
cleanly is a target that has already become the leader and an original
that has since been removed from the cluster, because there may be no
original left to hand leadership back to; that has to be refused rather
than reverted into an undefined state. The canceller holds the
original and target replica sets, reverts to the originals, reports
which target replicas are dropped, and refuses a cancel when no
original replica survives to take leadership back, and refuses to
cancel a reassignment that has already completed, since there is
nothing in flight to undo. It reports the replicas dropped by the
cancel, because those are brokers that did work copying a log now
thrown away, the cost of a reassignment started and abandoned rather
than left to finish."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class ReassignmentCancel:
    original: list[str]
    target: list[str]
    surviving: set[str] = field(default_factory=set)
    completed: bool = False

    def __post_init__(self) -> None:
        # by default every original replica is assumed to still be in the cluster
        if not self.surviving:
            self.surviving = set(self.original)

    def cancel(self) -> list[str]:
        if self.completed:
            raise Invalid("the reassignment already completed; nothing to undo")
        if not any(r in self.surviving for r in self.original):
            raise Invalid(
                "no original replica survives to take leadership back; "
                "cancelling would leave the partition in an undefined state"
            )
        # dropped targets are those in the target set but not an original
        return [r for r in self.target if r not in self.original]

    def reverted_replicas(self) -> list[str]:
        return list(self.original)

    def in_flight_union(self) -> list[str]:
        # while the move runs, replicas are the union of original and target
        seen: list[str] = list(self.original)
        for r in self.target:
            if r not in seen:
                seen.append(r)
        return seen

    def note(self) -> str:
        if self.completed:
            return "reassignment completed; nothing in flight to cancel"
        dropped = self.cancel()
        return (
            f"cancel reverts to {self.original}, dropping {dropped}; those "
            "brokers copied a log now thrown away, the cost of a reassignment "
            "started and abandoned"
        )
