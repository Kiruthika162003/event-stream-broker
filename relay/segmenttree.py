"""Segment tree: range-max over partitions with a point update, both logarithmic.

A monitor that must answer what is the worst lag among partitions
i through j, over and over, while individual lags keep changing, has
two poor options with a flat array: recompute the max of the range on
every query, linear in the range, or keep a single running max, which
cannot be maintained under a decrease because lowering the current
maximum leaves you not knowing the second largest. The segment tree
gives both operations a logarithm. It is a binary tree over the array
where each node holds the max of a contiguous range, leaves are single
elements, and a parent is the max of its two children. A point update
changes one leaf and walks up recomputing the parents on the path to
the root, a logarithm of nodes touched, so a decrease is handled
correctly because each affected parent is recomputed from both
children rather than from the old max alone. A range query descends
from the root, taking a node's stored max whole when its range lies
inside the query, recursing when it partly overlaps, and ignoring it
when it is disjoint, so it visits a logarithmic number of nodes rather
than every element. This is the structure behind a lag dashboard that
reports the worst partition in any range as lags stream in. The tree
builds over a fixed size, updates a leaf and repairs the path,
answers a range max, and refuses an index out of range and an
inverted query range, because a query whose low exceeds its high has
no meaning and would silently return the identity rather than signal
the caller's mistake. It reports the root, the max over the whole
array, the one value a running scalar could have tracked and the
reason the rest of the tree exists."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid

_NEG_INF = float("-inf")


@dataclass
class SegmentTree:
    size: int
    _tree: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.size < 1:
            raise Invalid("a segment tree needs at least one element")
        # a full binary tree stored in an array, 1-indexed, 2n covers n leaves;
        # an unreported partition has lag 0, so 0.0 is the honest default leaf
        self._tree = [0.0] * (2 * self.size)

    def update(self, index: int, value: float) -> None:
        if not 0 <= index < self.size:
            raise Invalid(f"index {index} is out of range 0..{self.size - 1}")
        pos = index + self.size
        self._tree[pos] = value
        pos //= 2
        while pos >= 1:
            # a parent is the max of its two children
            self._tree[pos] = max(self._tree[2 * pos], self._tree[2 * pos + 1])
            pos //= 2

    def range_max(self, low: int, high: int) -> float:
        if low > high:
            raise Invalid(
                f"range {low}..{high} is inverted; a low above the high has no "
                "meaning and would silently return the identity"
            )
        if not (0 <= low < self.size and 0 <= high < self.size):
            raise Invalid(f"range {low}..{high} falls outside 0..{self.size - 1}")
        result = _NEG_INF
        lo = low + self.size
        hi = high + self.size + 1
        while lo < hi:
            if lo & 1:
                result = max(result, self._tree[lo])
                lo += 1
            if hi & 1:
                hi -= 1
                result = max(result, self._tree[hi])
            lo //= 2
            hi //= 2
        return result

    def overall_max(self) -> float:
        return self._tree[1]

    def note(self) -> str:
        return (
            f"root max {self._tree[1]} over {self.size} element(s); the root is "
            "the one value a running scalar could track, the rest of the tree is "
            "what lets a decrease be handled and any subrange be queried"
        )
