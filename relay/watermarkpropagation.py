"""Watermark propagation: a follower learns the committed offset one round late.

The high watermark, the offset up to which records are committed
and readable, is computed by the leader as the lowest end offset
across the in-sync replicas, so only the leader knows the true
watermark at any instant. A follower learns it in the fetch
response: when a follower fetches records the leader also tells it
the current watermark, so the follower's knowledge of the
watermark is always one fetch round behind the leader's, because
between the follower's fetch and its next one the leader may have
advanced the watermark and the follower has not heard yet. This
lag is why a follower serving reads exposes a watermark slightly
below the leader's even when its log is fully caught up: it has
the records but not yet the news that they are committed. The
propagation model makes the lag concrete: a follower's exposed
watermark is the watermark carried in its last fetch response, and
the gap to the leader's current watermark is the records committed
since that response, which a consumer reading the follower cannot
see until the follower's next fetch round refreshes it. The model
refuses to let a follower expose a watermark above what its last
response carried, because a follower advancing its watermark ahead
of the news would expose records the leader has not confirmed
committed, the exact hazard the watermark exists to prevent. The
report states the propagation lag in rounds, because a consumer
choosing follower reads needs to know its view of committedness
refreshes only as often as the follower fetches.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class WatermarkView:
    leader_watermark: int
    last_response_watermark: int

    def __post_init__(self) -> None:
        if self.last_response_watermark > self.leader_watermark:
            raise Invalid(
                "a follower cannot expose a watermark above the "
                "leader's; that would confirm records the leader "
                "has not committed"
            )

    def follower_exposes(self) -> int:
        return self.last_response_watermark

    def propagation_gap(self) -> int:
        return self.leader_watermark - self.last_response_watermark

    def refresh(self, new_leader_watermark: int) -> None:
        if new_leader_watermark < self.last_response_watermark:
            raise Invalid(
                "the watermark only advances; a fetch response "
                "cannot carry a lower one than already seen"
            )
        self.leader_watermark = max(
            self.leader_watermark, new_leader_watermark
        )
        self.last_response_watermark = new_leader_watermark

    def describe(self) -> str:
        gap = self.propagation_gap()
        return (
            f"follower exposes {self.last_response_watermark}, "
            f"leader at {self.leader_watermark}: {gap} record(s) "
            "committed since the follower's last fetch, invisible "
            "to a follower reader until its next fetch round"
        )
