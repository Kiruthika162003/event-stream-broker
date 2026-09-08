"""Consistent hash: add a node and move a fraction of keys, not almost all.

Assigning keys to nodes by hashing the key modulo the node count is
simple and has a brutal failure mode: change the node count and
almost every key moves, because the modulo changes for nearly all
of them, so adding one broker to a ten-broker cluster reshuffles the
whole keyspace. Consistent hashing avoids that. Nodes and keys are
both hashed onto a ring, and a key belongs to the first node
clockwise from it, so adding a node captures only the keys between
it and the previous node, and removing a node hands its keys only to
the next node, leaving every other key where it was. The fraction
that moves is about one over the node count, not nearly all, which
is why consistent hashing is what systems reach for when nodes join
and leave often and reshuffling the world each time is unacceptable.
The evenness of the spread is improved with virtual nodes: each real
node is placed at several points on the ring rather than one, so a
node's share of the ring is the sum of several arcs and the law of
large numbers smooths the imbalance a single placement would leave.
The ring maps a key to its node by finding the first virtual node
clockwise, wrapping past the end back to the start, and it reports
what fraction of keys move when a node is added, the number that
justifies the added complexity over modulo. It refuses to map
against an empty ring, which has no node to answer, and refuses to
add a node already present, a duplicate that would double its share.
This package's partitions use modulo, chosen deliberately because a
partition's key must map to a fixed partition for ordering; consistent
hashing is the right tool for assigning shards to nodes that churn,
a different problem, and naming the distinction keeps each in its place.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class HashRing:
    vnodes: int = 3
    ring: dict[int, str] = field(default_factory=dict)
    nodes: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.vnodes < 1:
            raise Invalid("each node needs at least one virtual node")

    def _points(self, node: str) -> list[int]:
        return [
            (hash(f"{node}#{i}") & 0x7FFFFFFF) for i in range(self.vnodes)
        ]

    def add(self, node: str) -> None:
        if node in self.nodes:
            raise Invalid(f"node '{node}' already on the ring; a duplicate share")
        self.nodes.add(node)
        for p in self._points(node):
            self.ring[p] = node

    def remove(self, node: str) -> None:
        self.nodes.discard(node)
        self.ring = {p: n for p, n in self.ring.items() if n != node}

    def node_for(self, key: str) -> str:
        if not self.ring:
            raise Invalid("the ring is empty; no node to answer")
        h = hash(key) & 0x7FFFFFFF
        points = sorted(self.ring)
        for p in points:
            if p >= h:
                return self.ring[p]
        return self.ring[points[0]]  # wrap around

    def churn(self, keys: list[str], new_node: str) -> str:
        before = {k: self.node_for(k) for k in keys}
        self.add(new_node)
        moved = sum(1 for k in keys if self.node_for(k) != before[k])
        pct = moved / len(keys) * 100 if keys else 0
        return (
            f"adding '{new_node}' moved {moved}/{len(keys)} key(s) "
            f"({pct:.0f}%); modulo would move nearly all, this moves about "
            "one over the node count"
        )
