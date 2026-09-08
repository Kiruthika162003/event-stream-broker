"""Bloom filter: a cheap definitely-not-present check that never lies that way.

Some broker lookups can be skipped entirely if a key is known not
to be present, and a bloom filter answers that cheaply: it tells
you a key is definitely not in a set or possibly in it, using a bit
array far smaller than storing the keys themselves. Each key is
hashed by several independent hash functions to several bit
positions, and adding a key sets those bits; testing a key checks
those bits, and if any is unset the key was never added, a definite
no, while if all are set the key was probably added, a maybe. The
asymmetry is the whole value and the whole catch: there are no
false negatives, a key that was added always tests as present,
because its bits were set and never cleared, so a definitely-not
answer is always trustworthy and lets the caller skip a lookup
safely. But there are false positives, a key never added can have
all its bits set by other keys, so a maybe must be confirmed by the
real lookup, and the false-positive rate rises as the filter fills,
because more set bits make accidental all-set more likely. The
filter sizes that tradeoff: more bits and more hash functions lower
the false-positive rate at the cost of space and compute, and the
rate is predictable from the fill, so an operator can size a filter
for a target rate given the expected key count. This implementation
sets and tests bits with several hash functions, reports the
estimated false-positive rate from the fraction of bits set, and
refuses a zero-size filter or zero hash functions, which cannot
represent a set. It never removes a key, because clearing bits
would create false negatives, the one error a bloom filter must not
have, so a filter that must forget is rebuilt rather than cleared.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class BloomFilter:
    size_bits: int
    hash_count: int
    bits: set[int] = field(default_factory=set)
    added: int = 0

    def __post_init__(self) -> None:
        if self.size_bits < 1 or self.hash_count < 1:
            raise Invalid("a bloom filter needs positive size and hash count")

    def _positions(self, key: str) -> list[int]:
        positions = []
        for i in range(self.hash_count):
            h = hash(f"{i}:{key}") & 0x7FFFFFFF
            positions.append(h % self.size_bits)
        return positions

    def add(self, key: str) -> None:
        for pos in self._positions(key):
            self.bits.add(pos)
        self.added += 1

    def might_contain(self, key: str) -> bool:
        return all(pos in self.bits for pos in self._positions(key))

    def definitely_absent(self, key: str) -> bool:
        return not self.might_contain(key)

    def estimated_false_positive_rate(self) -> float:
        fraction_set = len(self.bits) / self.size_bits
        return fraction_set ** self.hash_count

    def report(self) -> str:
        rate = self.estimated_false_positive_rate()
        return (
            f"{self.added} key(s) in {self.size_bits} bit(s), "
            f"{len(self.bits)} set; estimated false-positive rate "
            f"{rate:.3f}; a maybe needs the real lookup, a no never lies"
        )
