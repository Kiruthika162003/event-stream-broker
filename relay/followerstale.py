"""Follower read staleness: reading a nearby replica trades freshness for cost.

Fetch-from-follower lets a consumer read a nearby replica instead
of the distant leader, saving cross-region cost, but a follower is
always a little behind the leader, so the read is a little stale,
and the question is how stale is acceptable. The staleness of a
follower read is exactly the follower's replication lag, the gap
between its high watermark and the leader's, so a consumer reading
a follower sees the world as of the follower's watermark, which is
bounded by how far behind the follower is allowed to fall before
eviction from the in-sync set. That eviction bound is the honesty
of the design: because a follower more than max-lag behind is
evicted, an in-sync follower's staleness is bounded by max-lag, so
a consumer reading any in-sync follower has a guaranteed freshness
floor. The analyzer computes the worst-case staleness a follower
read can have and refuses to serve a follower read to a consumer
that requires stronger freshness than the follower can guarantee,
because a consumer needing the absolute latest must read the
leader, and serving it a follower silently gives it stale data it
declared it could not tolerate. The report states the follower's
current staleness against the consumer's tolerance, because a
consumer choosing follower reads for cost needs to know the
freshness it is trading away is bounded and how large the bound
is, not discover during an incident that its nearby read was
minutes behind.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class FollowerRead:
    leader_watermark: int
    follower_watermark: int
    max_lag: int

    def __post_init__(self) -> None:
        if self.follower_watermark > self.leader_watermark:
            raise Invalid(
                "a follower cannot be ahead of the leader"
            )

    def staleness(self) -> int:
        return self.leader_watermark - self.follower_watermark

    def in_sync(self) -> bool:
        return self.staleness() <= self.max_lag

    def may_serve(self, tolerance: int) -> str:
        if not self.in_sync():
            raise Invalid(
                f"this follower is {self.staleness()} behind, "
                f"past max-lag {self.max_lag}, and out of sync; "
                "it should not be serving reads at all"
            )
        if self.staleness() > tolerance:
            raise Invalid(
                f"the follower is {self.staleness()} stale but "
                f"the consumer tolerates {tolerance}; serving it "
                "would give stale data it declared it cannot "
                "tolerate, so it must read the leader"
            )
        return (
            f"follower read served: {self.staleness()} stale, "
            f"within the consumer's tolerance {tolerance} and the "
            f"max-lag ceiling {self.max_lag}"
        )
