"""Lag monitoring: the number that is a symptom or a trend, and the difference.

Consumer lag, the gap between a partition's committed offset and
its high watermark, is the most watched number in a streaming
system, and the most misread. A single lag reading is nearly
useless: lag of ten thousand is fine if the consumer is draining
it and a crisis if the consumer is falling further behind, and
the instantaneous number cannot tell the two apart. The monitor
tracks lag over time and computes the derivative: lag that is
flat or shrinking is a consumer keeping up, lag that is growing
is a consumer losing the race, and the time-to-drain, current
lag divided by the drain rate, is the number an operator can
actually act on, because "lag 10k, draining, empty in 4 minutes"
is a shrug and "lag 10k, growing, never empties" is a page. The
monitor refuses to alert on a single sample, because a lag spike
from one slow batch that immediately recovers is noise, and a
monitor that pages on noise trains its operators to ignore it,
which is how the real page gets missed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class LagMonitor:
    samples: list[tuple[int, int]] = field(default_factory=list)

    def observe(self, tick: int, lag: int) -> None:
        if lag < 0:
            raise Invalid("lag cannot be negative")
        if self.samples and tick <= self.samples[-1][0]:
            raise Invalid("samples must advance in time")
        self.samples.append((tick, lag))

    def drain_rate(self) -> float:
        if len(self.samples) < 2:
            raise Invalid("a rate needs at least two samples")
        first_tick, first_lag = self.samples[0]
        last_tick, last_lag = self.samples[-1]
        return (last_lag - first_lag) / (last_tick - first_tick)

    def verdict(self) -> str:
        if len(self.samples) < 2:
            raise Invalid(
                "one sample is a symptom, not a trend; the "
                "monitor does not alert on it"
            )
        slope = self.drain_rate()
        current = self.samples[-1][1]
        if slope <= 0:
            if current == 0:
                return "lag is zero; the consumer is caught up"
            if slope == 0:
                return (
                    f"lag {current}, flat; holding steady, not a "
                    "page"
                )
            ticks_to_empty = int(current / -slope)
            return (
                f"lag {current}, draining, empty in about "
                f"{ticks_to_empty} tick(s); a shrug, not a page"
            )
        return (
            f"lag {current}, growing at {slope:.0f}/tick; the "
            "consumer is losing the race and never empties, "
            "which is a page"
        )

    def should_page(self) -> bool:
        if len(self.samples) < 2:
            return False
        return self.drain_rate() > 0
