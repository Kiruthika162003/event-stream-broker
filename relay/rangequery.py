"""Range query: find the slice of a sorted index between two bounds, by halving.

A time-index scan for records between nine and ten, an offset-range
fetch, a lookup of all keys in a prefix, are all the same shape: a
sorted structure and a query for the contiguous slice whose keys
fall in a range. Done naively by scanning from the front, each
query costs the whole index, but because the keys are sorted the
two ends of the slice are found by binary search, the first key at
or after the low bound and the first key past the high bound, and
the slice between them is the answer, so a query over a million
entries touches only a logarithmic number to find the bounds plus
the entries actually returned. This is what makes a range read on a
large log cheap: the index localizes the range without reading
outside it. The query returns the entries in sorted order, which is
what a scan consumes, and it handles the empty result, a range
falling entirely between two adjacent keys or outside the index,
without error, because an empty range is a normal answer, not a
failure. The structure refuses a high bound below the low bound, an
inverted range that asks for a slice that cannot exist and is a
caller bug rather than an empty result, distinguishing the two so a
mistake is caught rather than silently returning nothing. It also
refuses a query against an unsorted index, verifying the invariant
the binary search depends on, because a range query over unsorted
keys returns a wrong slice a caller would trust. It reports the
slice size against the index size, because a range read returning
most of the index is a scan in disguise, cheap only if the range is
narrow relative to the whole."
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class SortedIndex:
    keys: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        for i in range(1, len(self.keys)):
            if self.keys[i] < self.keys[i - 1]:
                raise Invalid(
                    f"index not sorted at position {i}; a range query over "
                    "unsorted keys returns a wrong slice"
                )

    def range(self, low: int, high: int) -> list[int]:
        if high < low:
            raise Invalid(
                f"high bound {high} is below low {low}; an inverted range is "
                "a caller bug, not an empty result"
            )
        start = bisect_left(self.keys, low)
        end = bisect_right(self.keys, high)
        return self.keys[start:end]

    def selectivity(self, low: int, high: int) -> str:
        slice_size = len(self.range(low, high))
        total = len(self.keys)
        if total == 0:
            return "empty index; nothing to scan"
        frac = slice_size / total * 100
        return (
            f"{slice_size}/{total} entries in range ({frac:.0f}%); a range "
            "returning most of the index is a scan in disguise, cheap only "
            "when narrow"
        )
