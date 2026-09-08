"""Fenwick tree: prefix sums that update and query in log time, not linear.

A running total over an array, the cumulative bytes up to a
partition, the rank of an offset among many, is easy to query if
the array never changes, precompute the prefix sums, but expensive
to keep current when the underlying values change, because updating
one value shifts every prefix sum after it. A Fenwick tree, or
binary indexed tree, gives both a logarithmic update and a
logarithmic prefix-sum query by storing partial sums over ranges
whose sizes are powers of two, so a single value change touches
only the logarithmic number of partial sums that cover it, and a
prefix sum is assembled from a logarithmic number of them. The
trick is the indexing: each position holds the sum of a range
ending at it whose length is the lowest set bit of the index, so
updating walks up by adding the lowest set bit and querying walks
down by removing it, both taking as many steps as there are set
bits, at most the logarithm. This makes a Fenwick tree the right
structure for a statistic that must stay current under a stream of
updates, where recomputing prefix sums from scratch each time would
cost the whole array. The tree updates a position by a delta,
queries the prefix sum up to a position, and derives a range sum as
the difference of two prefix sums. It refuses an index outside its
range, one-based because the lowest-set-bit walk needs a nonzero
index, and it reports the total, the prefix sum over the whole
range, which is the running grand total the tree maintains for free
alongside every partial query."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class FenwickTree:
    size: int
    _tree: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.size < 1:
            raise Invalid("a Fenwick tree needs a positive size")
        if not self._tree:
            self._tree = [0] * (self.size + 1)

    def update(self, index: int, delta: int) -> None:
        if not 1 <= index <= self.size:
            raise Invalid(f"index {index} outside 1..{self.size}")
        i = index
        while i <= self.size:
            self._tree[i] += delta
            i += i & (-i)  # add the lowest set bit

    def prefix_sum(self, index: int) -> int:
        if not 0 <= index <= self.size:
            raise Invalid(f"index {index} outside 0..{self.size}")
        total = 0
        i = index
        while i > 0:
            total += self._tree[i]
            i -= i & (-i)  # remove the lowest set bit
        return total

    def range_sum(self, low: int, high: int) -> int:
        if low > high:
            raise Invalid("range low cannot exceed high")
        return self.prefix_sum(high) - self.prefix_sum(low - 1)

    def total(self) -> str:
        return (
            f"grand total {self.prefix_sum(self.size)}; maintained for free "
            "alongside every partial query, no full recompute"
        )
