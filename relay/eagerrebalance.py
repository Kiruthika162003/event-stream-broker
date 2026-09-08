"""Eager rebalance: everyone drops everything, and that is the cost cooperative cut.

The original rebalance protocol is eager: when membership changes,
every member revokes every partition it holds before the new
assignment is computed, so the whole group stops consuming for the
duration of the rebalance, and only after the sync phase does each
member resume with its new set. This is simple and correct, and it
has one blunt cost: a member whose assignment did not change still
gave up its partitions and got them back, pausing for a rebalance
that moved nothing of its own. In a large group a single member
joining triggers a stop-the-world pause across every member, even
though almost every partition ends up back where it was. The model
makes that waste visible by computing, for an eager rebalance, how
many partitions actually changed owner against how many were
revoked, and the gap is the partitions that stopped for no reason.
This is exactly the cost the cooperative protocol was designed to
cut: cooperative revokes only the partitions that move, so the
pause is proportional to the change rather than to the group size.
The model refuses to report an eager rebalance as free when
partitions were revoked, because the whole point is that eager is
never free even when the assignment is stable, and it refuses a
revoked count smaller than the moved count, an impossible state
since a moved partition must first be revoked. The report states
the unnecessary-pause ratio, the revoked-but-unchanged partitions
over the total, because a group with a high ratio churning often is
paying stop-the-world pauses for almost nothing and is the clearest
candidate for switching to cooperative.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class EagerRebalance:
    total_partitions: int
    moved_partitions: int

    def __post_init__(self) -> None:
        if self.total_partitions < 0 or self.moved_partitions < 0:
            raise Invalid("counts cannot be negative")
        if self.moved_partitions > self.total_partitions:
            raise Invalid(
                "more partitions moved than exist; a moved partition "
                "must first be among those revoked"
            )

    def revoked(self) -> int:
        # eager revokes everything
        return self.total_partitions

    def paused_for_nothing(self) -> int:
        return self.total_partitions - self.moved_partitions

    def unnecessary_ratio(self) -> float:
        if self.total_partitions == 0:
            return 0.0
        return self.paused_for_nothing() / self.total_partitions

    def report(self) -> str:
        wasted = self.paused_for_nothing()
        ratio = self.unnecessary_ratio()
        return (
            f"eager revoked all {self.total_partitions}, only "
            f"{self.moved_partitions} moved: {wasted} partition(s) "
            f"paused for nothing ({ratio:.0%}); a high ratio is the "
            "clearest candidate for cooperative"
        )
