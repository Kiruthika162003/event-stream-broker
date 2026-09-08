"""Replica lag time: in-sync is measured in time since caught up, not offsets.

Whether a follower is in the in-sync set decides whether its
acknowledgement counts toward a committed write, and the measure
that decides it was once the offset distance behind the leader, but
offset distance is the wrong measure under bursty load. A follower
that is perfectly healthy but a few thousand offsets behind during a
traffic spike would be evicted by an offset threshold, even though
it is fetching as fast as it can and will catch up the moment the
spike passes, and evicting a healthy follower shrinks the in-sync
set and weakens durability exactly when load is highest. The time
measure fixes this: a follower is in-sync if it has caught up to the
leader's end offset at some point within the lag-time window, so a
follower that keeps reaching the leader's log end, even while the
end keeps moving, stays in-sync no matter how many offsets a burst
put between them momentarily. A follower falls out only if it has
not caught up for longer than the window, which means it is not
keeping pace at all, a stuck or failing follower rather than a
briefly-behind healthy one. The tracker records, per follower, the
last time it caught up to the leader's end, and evicts a follower
whose last-caught-up time is older than the window. It refuses a
caught-up timestamp in the future, a clock error that would keep a
dead follower in-sync forever, and it treats a follower that has
never caught up as out until it does, not in on the benefit of the
doubt. The report states each follower's time since last caught up
against the window, because a follower creeping toward the window is
one whose fetch is slowing, the warning before it drops from the
in-sync set and durability quietly narrows.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class IsrByTime:
    lag_window: int
    caught_up_at: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.lag_window < 1:
            raise Invalid("the lag window must be positive")

    def caught_up(self, follower: str, now: int) -> None:
        if follower in self.caught_up_at and now < self.caught_up_at[follower]:
            raise Invalid(
                "caught-up time went backwards; a clock error would "
                "keep a dead follower in-sync forever"
            )
        self.caught_up_at[follower] = now

    def in_sync(self, follower: str, now: int) -> bool:
        last = self.caught_up_at.get(follower)
        if last is None:
            return False
        return now - last <= self.lag_window

    def evict(self, now: int) -> list[str]:
        return [
            f
            for f, last in self.caught_up_at.items()
            if now - last > self.lag_window
        ]

    def report(self, follower: str, now: int) -> str:
        last = self.caught_up_at.get(follower)
        if last is None:
            return f"{follower} has never caught up; out until it does"
        since = now - last
        return (
            f"{follower} last caught up {since} ago against a "
            f"{self.lag_window} window; creeping toward it is a "
            "slowing fetch, the warning before durability narrows"
        )
