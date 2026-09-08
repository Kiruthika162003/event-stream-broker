"""Quickselect: the k-th smallest without sorting the whole batch.

Reporting a percentile latency, the p99 of a batch of request times,
does not need the batch sorted, only the one value at the ninety-ninth
percentile rank. Sorting to find it does more work than the question
asks, order log n, when the answer is reachable in linear time on
average. Quickselect is that shortcut. It borrows quicksort's
partition step, choosing a pivot and splitting the values into those
below it and those above, but then it recurses into only the one side
that contains the rank it is looking for, discarding the other side
entirely rather than sorting it. Because each step throws away a
fraction of the values, the expected work is linear, a constant factor
over a single scan, where a full sort would pay the logarithm on
values it never needed to order. The rank it seeks maps directly from
a percentile: the p-th percentile of n values is the value at rank
p times n over a hundred, so p99 of a thousand latencies is the value
that would sit at rank 990 if sorted, found without the sort. The
selector finds the k-th smallest by zero-based rank, computes a
percentile by converting it to a rank first, and refuses a rank out of
range and an empty batch, because there is no k-th smallest of nothing
and a rank past the end names a value that does not exist. It uses a
median-of-three pivot to avoid the sorted-input worst case that a naive
first-element pivot degrades into, the quadratic blowup that would make
the shortcut slower than the sort it replaced, and its result is
checked against a full sort in the tests so the shortcut is trusted
only where it is shown to agree."
"""

from __future__ import annotations

from relay.errors import Invalid


def _median_of_three(values: list[float], lo: int, hi: int) -> float:
    mid = (lo + hi) // 2
    trio = sorted((values[lo], values[mid], values[hi]))
    return trio[1]


def kth_smallest(values: list[float], k: int) -> float:
    if not values:
        raise Invalid("there is no k-th smallest of an empty batch")
    if not 0 <= k < len(values):
        raise Invalid(f"rank {k} is out of range 0..{len(values) - 1}")
    data = list(values)
    lo, hi = 0, len(data) - 1
    while lo < hi:
        pivot = _median_of_three(data, lo, hi)
        # partition around the pivot: below on the left, above on the right
        left, right = lo, hi
        while left <= right:
            while data[left] < pivot:
                left += 1
            while data[right] > pivot:
                right -= 1
            if left <= right:
                data[left], data[right] = data[right], data[left]
                left += 1
                right -= 1
        # recurse into only the side holding rank k
        if k <= right:
            hi = right
        elif k >= left:
            lo = left
        else:
            return data[k]
    return data[lo]


def percentile(values: list[float], p: float) -> float:
    if not 0 <= p <= 100:
        raise Invalid(f"percentile {p} is outside 0..100")
    if not values:
        raise Invalid("there is no percentile of an empty batch")
    # the p-th percentile is the value at rank p*n/100, clamped to the last
    rank = min(len(values) - 1, int(p / 100 * len(values)))
    return kth_smallest(values, rank)


def note(values: list[float]) -> str:
    return (
        f"selecting over {len(values)} value(s) in linear time on average; a "
        "full sort would pay the logarithm on values the percentile never needs"
    )
