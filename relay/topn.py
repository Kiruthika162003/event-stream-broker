"""Top N: keep the highest-scoring few without sorting everything.

Reporting the top few of something, the ten hottest partitions, the
five producers by volume, does not need the whole set sorted, only
the top N kept, and keeping just N is far cheaper than sorting
thousands to take the head. The structure is a bounded min-heap of
size N: the smallest of the current top N sits at the root, and a
new item is compared against it, entering the top N only if it beats
that smallest, in which case it replaces the root, and being
discarded otherwise, so each item costs a logarithmic heap
operation rather than a full re-sort. This keeps the memory bounded
at N regardless of how many items stream through, which is the
point when the full set is too large to hold, and it keeps the top
N exact, not approximate, unlike a sketch that trades exactness for
even less memory. The tracker offers each item with its score,
admits it if the heap is not yet full or its score beats the
current minimum, and evicts the minimum when full, and it returns
the top N in descending score order on request. It refuses an N
below one, which keeps nothing, and it handles ties at the boundary
by a stable rule, keeping the incumbent when scores tie, because
churning the set on equal scores would make the top N flap without
changing what it contains. It reports the current admission
threshold, the score an item must beat to enter, because a
threshold that has risen high means the top N is saturated with
strong entries and a new item needs a high score to displace one, a
useful signal that the leaderboard has stabilized."
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class TopN:
    n: int
    _heap: list[tuple[int, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.n < 1:
            raise Invalid("top-N keeps at least one item")

    def offer(self, item: str, score: int) -> bool:
        if len(self._heap) < self.n:
            heapq.heappush(self._heap, (score, item))
            return True
        if score > self._heap[0][0]:
            heapq.heapreplace(self._heap, (score, item))
            return True
        return False

    def top(self) -> list[tuple[str, int]]:
        ordered = sorted(self._heap, key=lambda pair: pair[0], reverse=True)
        return [(item, score) for score, item in ordered]

    def threshold(self) -> str:
        if len(self._heap) < self.n:
            return (
                f"top-N not full ({len(self._heap)}/{self.n}); any item is "
                "admitted until it fills"
            )
        return (
            f"admission threshold {self._heap[0][0]}; an item must beat it to "
            "enter, and a high one means the leaderboard has stabilized"
        )
