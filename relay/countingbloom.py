"""Counting bloom: a bloom filter that can remove, by counting instead of setting.

A plain bloom filter cannot remove an element, because clearing its
bits might clear bits another element also set, creating a false
negative. A counting bloom filter fixes that by storing a small
counter at each position instead of a single bit: adding an element
increments the counters at its hash positions, removing decrements
them, and the element is considered present if all its counters are
above zero. Because a counter records how many elements set that
position, decrementing on remove takes away only this element's
contribution and leaves the others', so removal no longer risks a
false negative, the capability a plain bloom lacks. The cost is
memory: a counter is several bits where a bloom used one, so a
counting bloom is a few times larger for the same false-positive
rate, the price of deletion. Two hazards come with the counters.
Saturation: a counter that hits its maximum cannot be incremented
further, and once saturated it cannot be safely decremented either,
because it lost track of the true count, so a saturated counter is
left pinned, which can leak a small false-positive over time.
And a remove of an element never added would decrement counters
other elements set, corrupting them into false negatives, so it
must be refused. The filter increments on add, decrements on
remove, tests all-positive for membership, and refuses a remove of
an absent element and an increment past the counter maximum. It
reports the saturated-counter count, because saturation accumulating
is a filter overfilled for its size, its deletion accuracy
degrading, the signal to resize before removals start missing."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class CountingBloom:
    size: int
    hash_count: int
    max_count: int = 15
    counters: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.size < 1 or self.hash_count < 1:
            raise Invalid("size and hash count must be positive")
        if not self.counters:
            self.counters = [0] * self.size

    def _positions(self, key: str) -> list[int]:
        return [(hash(f"{i}:{key}") & 0x7FFFFFFF) % self.size for i in range(self.hash_count)]

    def add(self, key: str) -> None:
        for pos in self._positions(key):
            if self.counters[pos] < self.max_count:
                self.counters[pos] += 1

    def might_contain(self, key: str) -> bool:
        return all(self.counters[pos] > 0 for pos in self._positions(key))

    def remove(self, key: str) -> None:
        if not self.might_contain(key):
            raise Invalid(
                f"'{key}' is not present; removing it would decrement counters "
                "other elements set, corrupting them into false negatives"
            )
        for pos in self._positions(key):
            if 0 < self.counters[pos] < self.max_count:
                self.counters[pos] -= 1

    def saturation(self) -> str:
        pinned = sum(1 for c in self.counters if c >= self.max_count)
        return (
            f"{pinned} counter(s) saturated; accumulating saturation is a "
            "filter overfilled for its size, deletion accuracy degrading, "
            "resize before removals start missing"
        )
