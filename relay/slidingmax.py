"""Sliding max: the window's peak in constant time, with a monotonic deque.

Tracking the maximum over a sliding window, the peak request rate in
the last minute, the highest latency in the recent window, done
naively rescans the whole window on every step, costing the window
size per element. A monotonic deque does it in amortized constant
time per element by keeping only the values that could still be the
maximum. The idea: when a new value arrives, any older value in the
window smaller than it can never be the maximum again, because the
new value is larger and will outlive them, so they are discarded
from the back of the deque before the new value is added. The deque
thus holds a decreasing sequence of values, and the front is always
the current window maximum. As the window slides forward, a value
that has fallen out of the window is dropped from the front if it is
the one expiring. Each value is added and removed at most once, so
the total work is linear over the stream, amortized constant per
element, however large the window. The structure holds indices with
their values so it knows when a front value has slid out of the
window, and it exposes the current maximum as the front. It refuses
a window size below one, which holds no values, and refuses to
query the maximum of an empty window, a normal state at the start
before the window fills that the caller handles rather than reading
a stale peak. It reports how many values the deque holds against the
window size, because a deque nearly as long as the window is a
window of increasing values where nothing can be discarded, the
worst case where the deque saves nothing, while a short deque is the
common case of a few peaks dominating."
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class SlidingMax:
    window: int
    _deque: deque[tuple[int, int]] = field(default_factory=deque)
    _index: int = -1

    def __post_init__(self) -> None:
        if self.window < 1:
            raise Invalid("the window must hold at least one value")

    def push(self, value: int) -> None:
        self._index += 1
        # drop smaller values from the back: they can never be the max again
        while self._deque and self._deque[-1][1] <= value:
            self._deque.pop()
        self._deque.append((self._index, value))
        # drop the front if it has slid out of the window
        if self._deque[0][0] <= self._index - self.window:
            self._deque.popleft()

    def maximum(self) -> int:
        if not self._deque:
            raise Invalid("the window is empty; no maximum yet")
        return self._deque[0][1]

    def report(self) -> str:
        held = len(self._deque)
        if held >= self.window:
            return (
                f"deque holds {held}/{self.window}; an increasing window where "
                "nothing can be discarded, the worst case saving nothing"
            )
        return (
            f"deque holds {held}/{self.window}; a few peaks dominate, the "
            "common case the monotonic deque is built for"
        )
