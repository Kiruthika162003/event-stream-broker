"""Running median: two heaps track the middle, and outliers do not move it.

The median is a more honest center than the mean for latencies,
because a few extreme slow requests drag the mean up while the
median, the middle value, barely moves, so the median reports what a
typical request saw where the mean reports something no request saw.
Computing a running median over a stream without re-sorting on every
add is the two-heap trick. A max-heap holds the lower half of the
values seen and a min-heap holds the upper half, and they are kept
balanced so their sizes differ by at most one. The median is then
the top of the larger heap, or the average of the two tops when the
halves are equal, both available in constant time because the tops
are exactly the two middle values. Adding a value places it in the
half it belongs to, compared against the current tops, and then
rebalances by moving one value across if a half grew too big, each a
logarithmic heap operation, so the running median costs a logarithm
per value rather than a re-sort. This is the structure behind a
latency monitor that reports the median as it streams, robust to the
outliers that would distort a running mean. The tracker adds a value
to the correct half, rebalances, and returns the median, and it
refuses to read the median before any value is added, an undefined
state the caller handles. It reports the two heap sizes, because a
persistent imbalance would be a rebalancing bug, the invariant the
constant-time median rests on visibly held."
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class RunningMedian:
    # lower half as a max-heap (store negated), upper half as a min-heap
    _lower: list[int] = field(default_factory=list)
    _upper: list[int] = field(default_factory=list)

    def add(self, value: int) -> None:
        if not self._lower or value <= -self._lower[0]:
            heapq.heappush(self._lower, -value)
        else:
            heapq.heappush(self._upper, value)
        self._rebalance()

    def _rebalance(self) -> None:
        # keep sizes within one, lower allowed to hold the extra
        if len(self._lower) > len(self._upper) + 1:
            heapq.heappush(self._upper, -heapq.heappop(self._lower))
        elif len(self._upper) > len(self._lower):
            heapq.heappush(self._lower, -heapq.heappop(self._upper))

    def median(self) -> float:
        if not self._lower:
            raise Invalid("no values yet; the median is undefined")
        if len(self._lower) > len(self._upper):
            return float(-self._lower[0])
        return (-self._lower[0] + self._upper[0]) / 2

    def balance(self) -> str:
        return (
            f"lower {len(self._lower)}, upper {len(self._upper)}; a persistent "
            "imbalance would be a rebalancing bug, the invariant the constant-"
            "time median rests on"
        )
