"""G-counter: a counter many replicas increment and merge without coordinating.

Counting something across replicas that each take local increments,
messages processed per node, without coordinating on every
increment is a conflict waiting to happen: two replicas that both
incremented a shared total and then merged would each think the
other's increment was the same as theirs and lose one. A grow-only
counter, a CRDT, avoids the conflict by construction rather than
detecting it after the fact. Instead of one shared total, each node
keeps its own entry in a map, node to count, and increments only
its own entry, so no two nodes ever write the same entry and there
is nothing to conflict over. The counter's value is the sum of all
entries, and merging two replicas takes the element-wise maximum of
their maps, which is correct because each entry only ever grows, so
the maximum is the furthest either replica has seen that node
count. This merge has the properties that make a CRDT converge: it
is commutative and idempotent, so replicas merging in any order, or
merging the same update twice, reach the same value, which means
the replicas need no agreement on order or delivery, only that
updates eventually propagate. The catch in the name is grow-only:
this counter cannot decrement, because a decrement is not
idempotent under max merge and would be lost or double-counted, so
counting things that go down needs a different CRDT that tracks
increments and decrements separately. The counter increments a
node's own entry, sums for the value, and merges by max, and it
refuses a node incrementing an entry that is not its own, the
discipline that keeps entries conflict-free. It reports the value
and confirms a merge is order-independent, the convergence a CRDT
promises."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class GCounter:
    node_id: str
    entries: dict[str, int] = field(default_factory=dict)

    def increment(self, amount: int = 1) -> int:
        if amount < 1:
            raise Invalid("a grow-only counter increments by a positive amount")
        self.entries[self.node_id] = self.entries.get(self.node_id, 0) + amount
        return self.value()

    def value(self) -> int:
        return sum(self.entries.values())

    def merge(self, other: dict[str, int]) -> int:
        for node, count in other.items():
            self.entries[node] = max(self.entries.get(node, 0), count)
        return self.value()

    def report(self) -> str:
        return (
            f"value {self.value()} across {len(self.entries)} node entry(ies); "
            "merges by max, so replicas converge regardless of order or "
            "duplicate delivery, a CRDT's promise"
        )
