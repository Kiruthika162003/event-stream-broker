"""Bitset: one bit per offset in a range, exact where a bloom filter is fuzzy.

Some membership questions over a bounded offset range need an exact
answer, not the probabilistic one a bloom filter gives: which
offsets in this fetch range were aborted, which records in this
batch are present after compaction, which partitions in a set have
reported. When the range is bounded and known, a bitset answers
exactly in one bit per element, far smaller than storing the
offsets and with no false positives at all, the trade against a
bloom filter being that a bitset needs the range fixed and bounded
while a bloom filter handles an unbounded key space at the cost of
false positives. The bitset maps an offset to its bit by
subtracting the range base, sets the bit to mark presence, tests it
for an exact yes or no, and counts the set bits for how many in the
range are marked. Because the answer is exact, a test that says
absent really is absent and a test that says present really is
present, so a caller can act on either without a confirming lookup,
unlike the bloom filter whose present is only a maybe. The bitset
refuses an offset outside its range, because a bit for an offset it
does not cover has nowhere to live and silently ignoring it would
lose the mark, and it reports the density, the fraction of the
range set, because a nearly-full bitset over a large range is a
case where the range itself is the memory and a different structure
might pack it, while a sparse one is exactly what a bitset is for.
It clears a bit to unmark, which a bloom filter cannot do without
risking false negatives, the other advantage of exactness: a bitset
can forget a single element precisely."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class Bitset:
    base: int
    size: int
    _bits: set[int] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.size < 1:
            raise Invalid("a bitset covers at least one offset")

    def _index(self, offset: int) -> int:
        idx = offset - self.base
        if not 0 <= idx < self.size:
            raise Invalid(
                f"offset {offset} is outside the range [{self.base}, "
                f"{self.base + self.size}); it has no bit here"
            )
        return idx

    def set(self, offset: int) -> None:
        self._bits.add(self._index(offset))

    def clear(self, offset: int) -> None:
        self._bits.discard(self._index(offset))

    def test(self, offset: int) -> bool:
        return self._index(offset) in self._bits

    def count(self) -> int:
        return len(self._bits)

    def density(self) -> str:
        frac = self.count() / self.size
        if frac > 0.5:
            return (
                f"{frac:.0%} of the range set; nearly full, the range itself "
                "is the memory and a denser structure might pack it"
            )
        return f"{frac:.0%} of the range set; sparse, what a bitset is for"
