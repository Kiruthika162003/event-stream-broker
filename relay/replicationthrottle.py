"""Replication throttle: a catching-up follower must not starve the leader.

When a follower falls far behind, after a restart or a long
partition, it needs to catch up by fetching a large backlog, and
an unthrottled catch-up fetch competes with live produce and
consume traffic for the leader's network and disk. The pathology
is a feedback loop: the follower is behind, so it fetches hard,
which slows the leader, which makes more followers fall behind,
which makes them fetch hard too, and a cluster that was briefly
degraded becomes fully saturated. The throttle caps catch-up
fetch rate separately from live replication rate, so a follower
rejoining after maintenance catches up at a bounded pace that
leaves headroom for the traffic the cluster exists to serve. The
subtlety the throttle must get right is that it applies to
catch-up, the backlog below the leader's recent history, but not
to the steady tail, because throttling the tail would keep a
healthy follower permanently behind and defeat replication. So
the throttle distinguishes a follower fetching old data, which is
catch-up and throttled, from one fetching the newest data, which
is normal and unthrottled, by where in the log the fetch points.
The report states catch-up ETA under the throttle, because an
operator draining a broker needs to know whether catch-up
finishes in minutes or days before deciding to wait or intervene.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class ReplicationThrottle:
    catchup_rate: int
    catchup_boundary: int

    def __post_init__(self) -> None:
        if self.catchup_rate < 1:
            raise Invalid("the catch-up rate must be positive")

    def is_catchup(self, fetch_offset: int) -> bool:
        return fetch_offset < self.catchup_boundary

    def rate_for(self, fetch_offset: int) -> str:
        if self.is_catchup(fetch_offset):
            return (
                f"throttled at {self.catchup_rate}/tick: fetch "
                f"at {fetch_offset} is below the catch-up "
                f"boundary {self.catchup_boundary}, backlog that "
                "must leave headroom for live traffic"
            )
        return (
            f"unthrottled: fetch at {fetch_offset} is the steady "
            "tail, and throttling the tail keeps a healthy "
            "follower permanently behind"
        )

    def catchup_eta(
        self, follower_offset: int, leader_offset: int
    ) -> str:
        if follower_offset > leader_offset:
            raise Invalid("a follower cannot be ahead of the leader")
        backlog = self.catchup_boundary - follower_offset
        if backlog <= 0:
            return "no catch-up needed; the follower is in the tail"
        ticks = -(-backlog // self.catchup_rate)
        return (
            f"catch-up of {backlog} record(s) at "
            f"{self.catchup_rate}/tick finishes in about {ticks} "
            "tick(s); the number an operator needs before "
            "deciding to wait or intervene"
        )
