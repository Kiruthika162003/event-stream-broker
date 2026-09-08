"""Reassignment throttle: cap the move rate so rebalancing spares live traffic.

Moving a partition to a new broker means copying its whole log across
the network, and a large reassignment left unthrottled will saturate
the inter-broker link and starve the ordinary replication that keeps
followers in sync, so the cure for an unbalanced cluster becomes an
outage. The throttle caps the bytes per second that reassignment
traffic may use, leaving the rest of the link for live replication.
The tradeoff is direct and worth stating plainly: a lower throttle is
gentler on live traffic but stretches the move out longer, and the
completion time is simply the bytes to move divided by the throttle
rate. That formula is the whole planning tool. An operator who needs
the move done in an hour can compute the throttle that achieves it and
see whether that rate leaves enough headroom for live traffic, or
learn that it does not and that the move and the workload cannot both
be satisfied at once. The throttle must be set below the link capacity,
because a throttle at or above capacity is not a throttle at all and
leaves nothing for live traffic, and it must be positive, because a
zero rate never completes. The planner holds the bytes to move, the
throttle rate, and the link capacity, estimates the completion time,
reports the headroom left for live traffic, and refuses a throttle
that meets or exceeds capacity or is not positive. It states the
estimate and the headroom together, because the two are the both sides
of the one decision, how long the move takes against how much the
cluster keeps for the work it is actually there to do."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class ReassignmentThrottle:
    bytes_to_move: int
    throttle_bytes_per_sec: float
    link_capacity_bytes_per_sec: float

    def __post_init__(self) -> None:
        if self.throttle_bytes_per_sec <= 0:
            raise Invalid("the throttle must be positive; a zero rate never completes")
        if self.throttle_bytes_per_sec >= self.link_capacity_bytes_per_sec:
            raise Invalid(
                f"throttle {self.throttle_bytes_per_sec} meets or exceeds link "
                f"capacity {self.link_capacity_bytes_per_sec}; that is not a "
                "throttle and leaves nothing for live traffic"
            )
        if self.bytes_to_move < 0:
            raise Invalid("bytes to move cannot be negative")

    def completion_seconds(self) -> float:
        return self.bytes_to_move / self.throttle_bytes_per_sec

    def headroom_bytes_per_sec(self) -> float:
        return self.link_capacity_bytes_per_sec - self.throttle_bytes_per_sec

    def throttle_for_deadline(self, seconds: float) -> float:
        # the rate that finishes the move within a deadline
        if seconds <= 0:
            raise Invalid("the deadline must be positive")
        needed = self.bytes_to_move / seconds
        if needed >= self.link_capacity_bytes_per_sec:
            raise Invalid(
                f"finishing in {seconds}s needs {needed:.0f} B/s, at or above "
                f"capacity {self.link_capacity_bytes_per_sec}; the move and the "
                "live workload cannot both be satisfied that fast"
            )
        return needed

    def note(self) -> str:
        return (
            f"move takes {self.completion_seconds():.0f}s at "
            f"{self.throttle_bytes_per_sec:.0f} B/s, leaving "
            f"{self.headroom_bytes_per_sec():.0f} B/s for live traffic; those "
            "two are the both sides of the one decision"
        )
