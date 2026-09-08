"""Reassignment: moving a replica is a copy that must not drown the cluster.

Adding a broker or draining one requires moving partition
replicas from broker to broker, and a replica move is not a
pointer update; it is copying the whole partition log across
the network while the partition keeps serving. The danger is
throughput: an unthrottled reassignment saturates the network
links the live traffic needs, turning a maintenance operation
into a latency incident, so every move runs under a byte-rate
throttle and the plan states how long it will take at that
rate, because a reassignment with no ETA is a reassignment
nobody can schedule around. The new replica is not counted
in-sync, and therefore cannot be elected leader, until it has
fully caught up, because promoting a half-copied replica loses
every record it has not yet fetched. Cancellation is safe by
construction: a move interrupted midway leaves the original
replica untouched, since the new replica only becomes real when
it is complete, so the abort is a delete of incomplete work,
never a gap in coverage.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class ReplicaMove:
    partition: int
    from_broker: str
    to_broker: str
    total_bytes: int
    throttle_bytes_per_tick: int
    copied_bytes: int = 0
    cancelled: bool = False

    def __post_init__(self) -> None:
        if self.throttle_bytes_per_tick < 1:
            raise Invalid(
                "an unthrottled move saturates the links live "
                "traffic needs; set a positive rate"
            )
        if self.from_broker == self.to_broker:
            raise Invalid("a replica does not move to itself")

    def eta_ticks(self) -> int:
        remaining = self.total_bytes - self.copied_bytes
        return -(-remaining // self.throttle_bytes_per_tick)

    def advance(self, ticks: int) -> str:
        if self.cancelled:
            raise Invalid("the move was cancelled")
        self.copied_bytes = min(
            self.total_bytes,
            self.copied_bytes
            + ticks * self.throttle_bytes_per_tick,
        )
        if self.caught_up():
            return (
                f"partition {self.partition} fully copied to "
                f"{self.to_broker}; now eligible for in-sync "
                "and election"
            )
        return (
            f"partition {self.partition}: {self.copied_bytes} "
            f"of {self.total_bytes} bytes, ETA "
            f"{self.eta_ticks()} tick(s); not in-sync until "
            "complete, because a half-copied replica loses what "
            "it has not fetched"
        )

    def caught_up(self) -> bool:
        return self.copied_bytes >= self.total_bytes

    def eligible_for_election(self) -> bool:
        return self.caught_up() and not self.cancelled

    def cancel(self) -> str:
        self.cancelled = True
        return (
            f"partition {self.partition} move cancelled; the "
            f"original on {self.from_broker} is untouched, so "
            "the abort deletes incomplete work, never coverage"
        )
