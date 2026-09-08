"""EMA rate: weight recent samples more, so the number moves when the load does.

A rate or latency reported as a simple average over a window has a
lag problem: every sample in the window counts equally, so a sudden
change is diluted by the older samples until it ages out, and the
reported number trails the real one by half the window. An
exponentially weighted moving average fixes the lag by weighting
recent samples more: each new sample moves the average toward it by
a fraction, the smoothing factor, and older samples fade
geometrically rather than dropping off a cliff, so the average
reacts to a change quickly while still smoothing the noise of any
single sample. The smoothing factor is the one knob and it trades
the two against each other: near one the average is almost the
latest sample, fast but noisy, and near zero it is almost the old
average, smooth but slow, so the factor is chosen from how quickly
the metric really changes against how noisy its samples are. The
EMA needs no window of stored samples, only the running average and
the factor, which is why it is the cheap choice for a metric
updated on every event, where keeping a window would cost memory
per metric. The estimator updates the average toward each sample by
the factor and reports the current value, and it refuses a factor
outside zero to one exclusive, since zero never moves and one keeps
no history, neither an average. It seeds the average with the first
sample rather than zero, because starting at zero would make the
first reading crawl up from nothing and misreport the rate until
enough samples pulled it to the truth, a cold-start bias the seed
removes.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class EmaRate:
    alpha: float
    value: float = 0.0
    _seeded: bool = False

    def __post_init__(self) -> None:
        if not 0 < self.alpha < 1:
            raise Invalid(
                "the smoothing factor must be in (0, 1); 0 never moves and 1 "
                "keeps no history, neither an average"
            )

    def update(self, sample: float) -> float:
        if not self._seeded:
            self.value = sample
            self._seeded = True
        else:
            self.value = self.alpha * sample + (1 - self.alpha) * self.value
        return self.value

    def current(self) -> float:
        if not self._seeded:
            raise Invalid("no samples yet; the average is undefined")
        return self.value

    def responsiveness(self) -> str:
        if self.alpha >= 0.5:
            return f"alpha {self.alpha}: fast to react, noisier"
        return f"alpha {self.alpha}: smooth, slower to react"
