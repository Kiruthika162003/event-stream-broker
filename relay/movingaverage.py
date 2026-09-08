"""Moving average: every sample in the window counts equally, and it lags for it.

A simple moving average is the mean of the last N samples, and it
is the honest baseline the exponentially weighted average elsewhere
in this package improves on. Its defining property is equal
weighting: every sample in the window counts the same, and a sample
older than the window counts not at all, dropping off sharply when
it ages out. That sharp drop-off is both its strength and its
weakness. The strength is that the SMA is exactly the average of a
known set of samples, easy to reason about and unbiased over the
window, with no decay constant to choose. The weakness is lag: a
sudden change in the underlying value is diluted by the older
samples still in the window until they age out, so the SMA trails
the real value by about half the window, and a spike that is real
looks smaller than it is until the window catches up. The other
artifact of the sharp drop-off is that a single extreme old sample
leaving the window jerks the average when it goes, an edge effect
the smooth decay of an EMA does not have. So the SMA suits a metric
where the window is a meaningful unit, the average over exactly the
last minute, and the EMA suits one where recency should be weighted
smoothly. The average keeps a fixed window of recent samples, drops
the oldest as a new one arrives, and returns their mean, and it
refuses a window size below one, which averages nothing, and the
average of an empty window, a normal start state before it fills.
It reports whether the window is full, because an SMA over a
not-yet-full window is a mean of fewer samples than the window
implies, the same young-window bias the ring buffer warned about,
overstating how settled the metric is."
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class MovingAverage:
    window: int
    _samples: deque[float] = field(default_factory=deque)

    def __post_init__(self) -> None:
        if self.window < 1:
            raise Invalid("the window must hold at least one sample")

    def add(self, sample: float) -> float:
        self._samples.append(sample)
        if len(self._samples) > self.window:
            self._samples.popleft()
        return self.average()

    def average(self) -> float:
        if not self._samples:
            raise Invalid("no samples yet; the average is undefined")
        return sum(self._samples) / len(self._samples)

    def is_full(self) -> bool:
        return len(self._samples) == self.window

    def fill_note(self) -> str:
        if not self.is_full():
            return (
                f"{len(self._samples)}/{self.window} samples; a mean of fewer "
                "than the window implies, overstating how settled the metric is"
            )
        return f"full window of {self.window}; the mean lags the real value by ~half the window"
