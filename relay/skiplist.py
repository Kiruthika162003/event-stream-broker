"""Skip list: a sorted structure that stays balanced by coin flips, not rotations.

A sorted structure needs to search, insert, and delete in
logarithmic time, and a balanced tree does it with careful rotation
logic that is easy to get subtly wrong. A skip list reaches the same
logarithmic bounds with no rotations at all, using randomness
instead. It is a stack of linked lists: the bottom list holds every
element in order, and each higher list is a sparser express lane
holding a random subset of the one below, so a search drops in at
the top, skips forward along the sparse express lanes until the next
element would overshoot, drops a level, and repeats, converging on
the target in a logarithmic number of steps on average. The
randomness is where an element's height comes from: when inserted,
an element is promoted to the next level up on a coin flip, again
and again until the coin says stop, so about half the elements reach
level one, a quarter level two, and so on, giving the express lanes
their geometric sparsity without any explicit balancing. Because the
balance is probabilistic, a pathological run of coin flips could
make it degenerate, but that is vanishingly unlikely and needs no
rebalancing code to guard against, which is the skip list's appeal:
the performance of a balanced tree with the simplicity of linked
lists. This implementation takes the coin flip as an injected
function so the structure is deterministic under test, searches by
descending the levels, inserts by splicing at each level up to the
element's height, and keeps the elements a set with no duplicates.
It reports the level distribution, because a skip list whose levels
are far from the geometric ideal is one whose coin was biased, the
randomness assumption the logarithmic bound rests on visibly
violated.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from relay.errors import Invalid

_MAX_LEVEL = 16


@dataclass
class _Node:
    value: int
    forward: list[_Node | None]


@dataclass
class SkipList:
    coin: Callable[[], bool]
    level: int = 0
    _head: _Node = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._head = _Node(value=-1, forward=[None] * (_MAX_LEVEL + 1))

    def _height(self) -> int:
        lvl = 0
        while self.coin() and lvl < _MAX_LEVEL:
            lvl += 1
        return lvl

    def insert(self, value: int) -> None:
        update: list[_Node] = [self._head] * (_MAX_LEVEL + 1)
        node = self._head
        for i in range(self.level, -1, -1):
            nxt = node.forward[i]
            while nxt is not None and nxt.value < value:
                node = nxt
                nxt = node.forward[i]
            update[i] = node
        after = node.forward[0]
        if after is not None and after.value == value:
            return  # no duplicates
        lvl = self._height()
        self.level = max(self.level, lvl)
        new = _Node(value=value, forward=[None] * (lvl + 1))
        for i in range(lvl + 1):
            new.forward[i] = update[i].forward[i]
            update[i].forward[i] = new

    def search(self, value: int) -> bool:
        node = self._head
        for i in range(self.level, -1, -1):
            nxt = node.forward[i]
            while nxt is not None and nxt.value < value:
                node = nxt
                nxt = node.forward[i]
        after = node.forward[0]
        return after is not None and after.value == value

    def in_order(self) -> list[int]:
        out: list[int] = []
        node = self._head.forward[0]
        while node is not None:
            out.append(node.value)
            node = node.forward[0]
        return out

    def level_counts(self) -> str:
        counts = [0] * (self.level + 1)
        node = self._head.forward[0]
        while node is not None:
            counts[len(node.forward) - 1] += 1
            node = node.forward[0]
        if not any(counts):
            raise Invalid("empty skip list has no levels")
        return (
            f"per-level counts {counts}; far from geometric halving is a "
            "biased coin, the randomness the logarithmic bound rests on"
        )
