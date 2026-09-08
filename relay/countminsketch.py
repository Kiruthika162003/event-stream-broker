"""Count-min sketch: estimate how often each key appears without storing keys.

Finding the hot keys in a stream, the ones producing most of the
traffic to a partition, would seem to need a counter per key, which
for a high-cardinality stream is as much memory as the data. A
count-min sketch estimates each key's count in fixed memory that
does not grow with the number of distinct keys, trading exactness
for a bounded space. It is a small grid of counters, several rows
each with its own hash function, and counting a key increments one
counter in every row at the position that key hashes to; estimating
a key's count reads those same counters and takes the minimum
across the rows. The minimum is the trick: each counter may be
inflated by other keys that hashed to the same position, so every
row's counter is an overestimate, but the smallest of them is the
least inflated, and because collisions only ever add, never
subtract, the sketch never underestimates. That one-sided error is
what makes it useful for heavy hitters: a key the sketch says is
rare really is rare, so a key it says is hot is worth checking,
while a key it might overcount is caught by the check. The sketch
counts and estimates in fixed rows and columns, and it reports the
overestimate it can make from its dimensions, because a sketch too
small for the stream's cardinality overcounts so much that every
key looks hot, defeating the purpose. It refuses zero rows or
columns, which cannot represent a count, and never returns a
negative estimate. The point of the approximation is scale: an
exact count is right and unbounded, the sketch is bounded and only
ever high, and for finding what to look at, bounded-and-high beats
exact-and-impossible.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class CountMinSketch:
    rows: int
    cols: int
    grid: list[list[int]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.rows < 1 or self.cols < 1:
            raise Invalid("a sketch needs positive rows and columns")
        if not self.grid:
            self.grid = [[0] * self.cols for _ in range(self.rows)]

    def _positions(self, key: str) -> list[int]:
        return [
            (hash(f"{r}:{key}") & 0x7FFFFFFF) % self.cols
            for r in range(self.rows)
        ]

    def add(self, key: str, count: int = 1) -> None:
        if count < 1:
            raise Invalid("count must be positive")
        for r, pos in enumerate(self._positions(key)):
            self.grid[r][pos] += count

    def estimate(self, key: str) -> int:
        return min(self.grid[r][pos] for r, pos in enumerate(self._positions(key)))

    def is_heavy_hitter(self, key: str, threshold: int) -> bool:
        return self.estimate(key) >= threshold

    def report(self) -> str:
        return (
            f"{self.rows}x{self.cols} sketch, never underestimates; too few "
            "columns for the stream's cardinality overcounts until every key "
            "looks hot, defeating the purpose"
        )
