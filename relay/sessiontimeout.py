"""Session timeout: the heartbeat interval must sit well under it, not near it.

A group member proves it is alive by heartbeating, and it is
evicted if the coordinator hears no heartbeat within the session
timeout. The relationship between the heartbeat interval and the
session timeout is a tuning that people get wrong in both
directions. Set the interval too close to the timeout, say equal,
and a single dropped heartbeat, one lost packet, one GC pause,
evicts the member, because there was no margin for a miss, so the
group suffers a false-positive eviction and a needless rebalance on
ordinary network jitter. Set it far too low and the member
heartbeats constantly, wasting network and coordinator work on beats
that prove nothing new. The rule of thumb is an interval around a
third of the session timeout, so the member sends about three
heartbeats per session window and the coordinator sees several
before giving up, tolerating one or two lost without evicting,
which turns a transient hiccup into a non-event rather than a
rebalance. The validator checks an interval against a timeout,
flags one too close to the timeout as risking false eviction and
one far too low as wasteful, and computes how many heartbeats fit in
a session window, the margin for a lost beat. It refuses an interval
at or above the session timeout, which guarantees eviction on the
first miss, and a non-positive timeout. It reports the beats-per-
window, because a group churning through rebalances with healthy
members is often one whose heartbeat interval is set too close to
its session timeout, evicting on jitter, a tuning fix rather than a
membership problem."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class SessionTiming:
    heartbeat_interval: int
    session_timeout: int

    def __post_init__(self) -> None:
        if self.session_timeout < 1 or self.heartbeat_interval < 1:
            raise Invalid("interval and timeout must be positive")
        if self.heartbeat_interval >= self.session_timeout:
            raise Invalid(
                "the heartbeat interval is at or above the session timeout; a "
                "single missed beat evicts the member, no margin at all"
            )

    def beats_per_window(self) -> float:
        return self.session_timeout / self.heartbeat_interval

    def tolerated_misses(self) -> int:
        return int(self.beats_per_window()) - 1

    def assess(self) -> str:
        beats = self.beats_per_window()
        if beats < 2:
            return (
                f"only {beats:.1f} beats per window; a dropped heartbeat "
                "evicts a healthy member, a false-positive rebalance on jitter"
            )
        if beats > 10:
            return (
                f"{beats:.0f} beats per window; heartbeating far more than "
                "needed, wasting network on beats that prove nothing new"
            )
        return (
            f"{beats:.0f} beats per window, tolerating {self.tolerated_misses()} "
            "lost; a transient hiccup is a non-event, not a rebalance"
        )
