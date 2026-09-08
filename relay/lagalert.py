"""Lag alerting: page on a backlog that is growing, not on one that is draining.

Consumer lag, the gap between a group's committed offset and the
partition end, is the most watched number on a streaming system,
and the most over-alerted. A threshold alert on absolute lag
pages constantly, because lag spikes are normal: a burst of
produces, a brief consumer pause, a rebalance, all push lag up
transiently and it drains on its own within seconds, so an alert
that fires on lag over a number wakes people for backlogs that
fixed themselves before they read the page. The alert that
matters is on the derivative, not the level: lag that is growing
sustained, the consumer falling behind faster than it catches up,
is the real problem, while lag that is high but shrinking is a
system recovering and needs no human. The alerter tracks lag over
a window and fires only when lag is both above a floor and
trending up over the window, because either alone is a false
alarm, a high but draining lag or a growing but negligible one.
It also computes time-to-drain from the trend, so an alert that
does fire carries the actionable number, this backlog clears in
an hour at the current rate, or never, which tells the responder
whether to wait or intervene. The alerter is explicit that a
never, a lag growing with no sign of turning, is the true
emergency, because a backlog that grows without bound eventually
exhausts retention and the consumer starts losing data it never
read, turning a latency problem into a loss one, which is the
escalation the derivative alert exists to catch early.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class LagAlerter:
    lag_floor: int
    window: int
    samples: list[tuple[int, int]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.window < 2:
            raise Invalid("the window needs at least two samples")

    def observe(self, tick: int, lag: int) -> None:
        if self.samples and tick <= self.samples[-1][0]:
            raise Invalid("samples must advance in time")
        if lag < 0:
            raise Invalid("lag cannot be negative")
        self.samples.append((tick, lag))
        if len(self.samples) > self.window:
            self.samples.pop(0)

    def trend(self) -> float:
        if len(self.samples) < 2:
            raise Invalid("a trend needs two samples")
        (t0, l0), (t1, l1) = self.samples[0], self.samples[-1]
        return (l1 - l0) / (t1 - t0)

    def evaluate(self) -> str:
        current = self.samples[-1][1]
        slope = self.trend()
        if current < self.lag_floor:
            return "no alert: lag is below the floor, negligible"
        if slope <= 0:
            return (
                f"no alert: lag {current} is high but draining at "
                f"{slope:.1f}/tick, a system recovering, no human "
                "needed"
            )
        drains_in = int(current / slope)
        return (
            f"ALERT: lag {current} growing at {slope:.1f}/tick, "
            f"clears in about {drains_in} tick(s) only if the "
            "trend reverses; not draining, and a backlog that "
            "grows unbounded exhausts retention and turns latency "
            "into loss"
        )
