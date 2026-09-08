"""Leader stickiness: a recovered broker waits before reclaiming, or it flaps.

Restoring leadership to a partition's preferred leader after a
failover keeps the cluster balanced, but doing it the instant the
preferred broker returns causes a problem when that broker is the
one that is unhealthy. A broker that crashes, recovers, reclaims
leadership, crashes again, and recovers again drags every partition
it prefers through a leadership change on each cycle, and a
leadership change is disruptive, so a flapping broker reclaiming
eagerly turns its own instability into cluster-wide churn.
Stickiness prevents it with a hold-down: after the preferred broker
returns and rejoins the in-sync set, leadership is not moved back to
it immediately, but only once it has stayed in-sync continuously for
a hold-down period, proving it is stable rather than about to flap
again. A broker that drops out of sync during the hold-down resets
the timer, so it must earn back leadership by demonstrating
stability, and a genuinely recovered broker reclaims after the
hold-down while a flapping one never stabilizes long enough to. This
trades a period of imbalance, the preferred leader idle while the
failover leader keeps serving, for avoiding the churn of premature
reclaim. The tracker records when the preferred broker became
in-sync, resets on a drop, and allows the reclaim only after the
hold-down has elapsed continuously. It refuses a reclaim before the
hold-down, naming that the broker has not proven stable, and reports
the time remaining, because a preferred leader whose hold-down keeps
resetting is a broker still flapping, the instability stickiness is
protecting the cluster from rather than a delay to shorten."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class LeaderStickiness:
    hold_down: int
    in_sync_since: int = -1

    def __post_init__(self) -> None:
        if self.hold_down < 1:
            raise Invalid("the hold-down must be positive")

    def became_in_sync(self, now: int) -> None:
        if self.in_sync_since < 0:
            self.in_sync_since = now

    def dropped_out(self) -> None:
        # a drop resets the stability timer; it must earn leadership again
        self.in_sync_since = -1

    def may_reclaim(self, now: int) -> bool:
        return self.in_sync_since >= 0 and now - self.in_sync_since >= self.hold_down

    def reclaim(self, now: int) -> str:
        if self.in_sync_since < 0:
            raise Invalid(
                "the preferred broker is not in sync; it cannot reclaim "
                "leadership at all"
            )
        if not self.may_reclaim(now):
            remaining = self.hold_down - (now - self.in_sync_since)
            raise Invalid(
                f"only in-sync for {now - self.in_sync_since} of the hold-down "
                f"{self.hold_down}; {remaining} left before it has proven "
                "stable, reclaiming now risks a flap"
            )
        return "preferred leader reclaims; it has been stably in-sync"

    def report(self, now: int) -> str:
        if self.in_sync_since < 0:
            return "preferred broker not in sync; the failover leader keeps serving"
        if self.may_reclaim(now):
            return "hold-down elapsed; safe to reclaim"
        return (
            f"{self.hold_down - (now - self.in_sync_since)} left in the hold-down; "
            "a hold-down that keeps resetting is a broker still flapping"
        )
