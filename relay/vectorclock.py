"""Vector clock: tell concurrent from ordered, which a Lamport clock cannot.

A Lamport clock gives every pair of events an order, but that order
lies about concurrency: two events that truly happened
independently on different nodes still get comparable timestamps,
so a smaller Lamport timestamp does not mean happens-before. A
vector clock fixes exactly that. Each node keeps not one counter
but a vector, one counter per node, and a node increments its own
entry on a local event and, on receiving a message, takes the
element-wise maximum of its vector and the message's before
incrementing its own. Comparing two vectors then distinguishes
three cases precisely: one happens-before another if every entry is
less than or equal and at least one is strictly less; they are
equal if all entries match; and they are concurrent if each has some
entry greater than the other, neither dominating. That third case
is what a Lamport clock cannot express and a vector clock can, and
it is what matters for detecting conflicts: two concurrent updates
to the same key are a conflict to resolve, not an ordering to
apply, and only a vector clock knows they were concurrent. The cost
is size: a vector clock grows with the number of nodes, so a
thousand-node system carries thousand-entry vectors on every event,
which is why vector clocks suit systems with modest node counts and
Lamport clocks or other schemes suit large ones. The clock ticks on
a local event, merges on a receive, and compares two vectors into
before, after, equal, or concurrent, and it treats a missing node
entry as zero so vectors from nodes that have not all met still
compare. It reports the comparison, because a pair reported
concurrent is a conflict the application must resolve, the outcome
the whole structure exists to surface."
"""

from __future__ import annotations

from dataclasses import dataclass, field

BEFORE = "before"
AFTER = "after"
EQUAL = "equal"
CONCURRENT = "concurrent"


@dataclass
class VectorClock:
    node_id: str
    vector: dict[str, int] = field(default_factory=dict)

    def tick(self) -> dict[str, int]:
        self.vector[self.node_id] = self.vector.get(self.node_id, 0) + 1
        return dict(self.vector)

    def merge(self, other: dict[str, int]) -> dict[str, int]:
        for node, count in other.items():
            self.vector[node] = max(self.vector.get(node, 0), count)
        self.vector[self.node_id] = self.vector.get(self.node_id, 0) + 1
        return dict(self.vector)

    @staticmethod
    def compare(a: dict[str, int], b: dict[str, int]) -> str:
        nodes = set(a) | set(b)
        a_less = a_greater = False
        for n in nodes:
            av, bv = a.get(n, 0), b.get(n, 0)
            if av < bv:
                a_less = True
            elif av > bv:
                a_greater = True
        if a_less and a_greater:
            return CONCURRENT
        if a_less:
            return BEFORE
        if a_greater:
            return AFTER
        return EQUAL

    @classmethod
    def conflict(cls, a: dict[str, int], b: dict[str, int]) -> bool:
        return cls.compare(a, b) == CONCURRENT
