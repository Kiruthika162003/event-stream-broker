"""Pause and resume: a consumer throttles a partition without leaving it.

A consumer subscribed to several partitions sometimes needs to
stop fetching one while it drains a slow downstream, a database
under load, an external API rate-limiting it, without giving up
ownership and triggering a rebalance. Pause is that control: the
partition stays assigned, its committed offset stays put, and
fetching simply stops until resume. The distinction that matters
is pause versus unsubscribe: unsubscribe leaves the group and
reassigns the partition, pause keeps the partition and merely
holds position, so a consumer applying backpressure to one slow
partition does not disturb the others or force the whole group
to rebalance. A paused partition still counts its lag, because a
consumer that paused a partition and forgot is a consumer whose
lag grows silently behind a deliberate decision, and the monitor
must not mistake a paused partition for a healthy one. Resume is
idempotent and pause is idempotent, because flow control called
twice by racing threads is normal and should be boring, not an
error.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class PartitionFlow:
    assigned: set[int]
    paused: set[int] = field(default_factory=set)

    def pause(self, partition: int) -> str:
        if partition not in self.assigned:
            raise Invalid(
                f"partition {partition} is not assigned; pause "
                "controls flow, it does not acquire ownership"
            )
        already = partition in self.paused
        self.paused.add(partition)
        if already:
            return f"partition {partition} already paused"
        return f"partition {partition} paused, position held"

    def resume(self, partition: int) -> str:
        if partition not in self.assigned:
            raise Invalid(
                f"partition {partition} is not assigned"
            )
        if partition not in self.paused:
            return f"partition {partition} was not paused"
        self.paused.discard(partition)
        return f"partition {partition} resumed"

    def fetchable(self) -> set[int]:
        return self.assigned - self.paused

    def is_paused(self, partition: int) -> bool:
        return partition in self.paused

    def lag_still_counts(self, paused_lag: dict[int, int]) -> str:
        watched = {
            p: lag
            for p, lag in paused_lag.items()
            if p in self.paused and lag > 0
        }
        if not watched:
            return "no paused partition is accruing lag"
        return (
            f"{len(watched)} paused partition(s) still accruing "
            "lag; a paused partition is not a healthy one, and "
            "the monitor must not mistake the two"
        )
