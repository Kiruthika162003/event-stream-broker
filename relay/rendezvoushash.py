"""Rendezvous hash: pick the node that scores highest for a key, no ring needed.

Rendezvous hashing, or highest-random-weight, assigns a key to a
node without the ring that consistent hashing maintains. For a key,
it computes a weight for every node by hashing the key together
with that node's id, and the key belongs to the node with the
highest weight. That is the whole algorithm, and it has the
property that makes it useful: when a node is added, a key moves to
it only if the new node scores higher for that key than the current
winner, which is a small fraction, and when a node is removed, each
of its keys goes to whichever remaining node scored second, again
without disturbing keys that node did not own, so the remapping on a
membership change is minimal, the same virtue as consistent hashing
but reached differently. Rendezvous needs no ring and no virtual
nodes to spread load evenly, because the per-node hash already
spreads keys uniformly across nodes, which makes it simpler to
reason about than a ring that needs virtual nodes to balance, at
the cost of scoring every node per lookup rather than a single ring
search, so it suits a modest node count where scoring all of them
is cheap. The hasher scores a key against every node and returns the
highest, and it can return a ranked list so a key's second choice,
its failover target, is known in advance. It refuses to place a key
with no nodes available, and it reports how many keys would move if
a given node joined, the minimal-disruption promise made concrete,
because a join that moved many keys would mean the hash is not
spreading them the way the algorithm assumes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class RendezvousHash:
    nodes: set[str] = field(default_factory=set)

    def _weight(self, key: str, node: str) -> int:
        return hash(f"{key}@{node}") & 0x7FFFFFFF

    def place(self, key: str) -> str:
        if not self.nodes:
            raise Invalid("no nodes available to place the key")
        return max(self.nodes, key=lambda n: self._weight(key, n))

    def ranked(self, key: str) -> list[str]:
        return sorted(self.nodes, key=lambda n: self._weight(key, n), reverse=True)

    def add(self, node: str) -> None:
        self.nodes.add(node)

    def remove(self, node: str) -> None:
        self.nodes.discard(node)

    def moved_if_added(self, keys: list[str], new_node: str) -> str:
        before = {k: self.place(k) for k in keys}
        self.add(new_node)
        moved = sum(1 for k in keys if self.place(k) != before[k])
        pct = moved / len(keys) * 100 if keys else 0
        return (
            f"adding '{new_node}' moves {moved}/{len(keys)} key(s) "
            f"({pct:.0f}%); a small fraction is the minimal-disruption promise, "
            "a large one means the hash is not spreading keys as assumed"
        )
