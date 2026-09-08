"""Replication lag in bytes: what a follower must transfer to catch up.

A follower behind the leader is measured three ways and they answer
different questions. Offset lag, the record count behind, does not
say how much data must move, because records vary in size. Time
lag, how long ago the follower's last record was, does not say how
long catching up will take, because that depends on transfer speed
not elapsed time. Byte lag, the volume of log the follower has not
yet fetched, is the one that bounds the catch-up: dividing the byte
lag by the replication bandwidth gives the time to catch up, the
number an operator actually needs when deciding whether a lagging
follower will recover on its own or needs intervention. The
calculator holds the leader's log-end byte position and the
follower's fetched byte position, computes the byte lag between
them, and estimates the catch-up time from the available
replication bandwidth, with the honest caveat that catch-up is a
moving target: while the follower fetches the backlog the leader
keeps writing, so the follower gains only the difference between the
bandwidth and the incoming write rate, and if the write rate meets
or exceeds the bandwidth the follower never catches up and the byte
lag grows without bound. The calculator surfaces that case
explicitly rather than returning a catch-up time that would never
arrive, because an operator told a follower will catch up in an hour
should instead be told it is falling behind and needs more
bandwidth or less load. It refuses a follower byte position ahead of
the leader's, impossible since the follower copies the leader, and
reports the lag in bytes and the projected catch-up or the
falling-behind verdict, so the decision is grounded in transfer
reality, not a record count that hides how much data is behind it."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class ByteLag:
    leader_bytes: int
    follower_bytes: int
    bandwidth_per_tick: float
    write_rate_per_tick: float

    def __post_init__(self) -> None:
        if self.follower_bytes > self.leader_bytes:
            raise Invalid("a follower cannot be ahead of the leader in bytes")
        if self.bandwidth_per_tick <= 0:
            raise Invalid("replication bandwidth must be positive")

    def lag_bytes(self) -> int:
        return self.leader_bytes - self.follower_bytes

    def net_catch_up_rate(self) -> float:
        return self.bandwidth_per_tick - self.write_rate_per_tick

    def falling_behind(self) -> bool:
        return self.net_catch_up_rate() <= 0

    def report(self) -> str:
        lag = self.lag_bytes()
        if self.falling_behind():
            return (
                f"{lag} byte(s) behind and falling: the write rate meets or "
                "exceeds the replication bandwidth, so it never catches up; "
                "needs more bandwidth or less load"
            )
        ticks = lag / self.net_catch_up_rate()
        return (
            f"{lag} byte(s) behind, catches up in ~{ticks:.0f} tick(s) at the "
            "net rate; a moving target since the leader keeps writing"
        )
