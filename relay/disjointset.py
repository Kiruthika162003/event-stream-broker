"""Disjoint set: group elements into classes, and answer same-group fast.

Grouping elements into equivalence classes, which partitions are
co-located on the same broker, which nodes are in the same rack,
which replicas form one connected component, is what a disjoint-set,
or union-find, structure does: it maintains a partition of elements
into disjoint groups and answers two questions fast, which group is
this in, and are these two in the same group. Union merges the
groups of two elements; find returns a group's representative, so
two elements are in the same group exactly when they have the same
representative. Done naively, find walks a chain of parents that can
grow long, but two optimizations make it nearly constant. Path
compression: find, having walked to the root, points every node on
the path directly at the root, so the next find is short, flattening
the tree as a side effect of querying it. Union by rank: union
attaches the shorter tree under the taller, keeping the trees
shallow rather than letting a chain form. Together they make a
sequence of operations run in almost linear time overall, the
near-constant per-operation cost that makes union-find the tool for
incremental grouping. The structure adds elements, unions two
groups, finds a representative with path compression, and answers
same-group by comparing representatives. It refuses a find of an
element never added, since it has no group, and reports the number
of distinct groups, because a grouping that collapses to one group
is everything connected while many groups is a fragmented set, and
the count tracks the merging as it happens without re-scanning."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class DisjointSet:
    parent: dict[str, str] = field(default_factory=dict)
    rank: dict[str, int] = field(default_factory=dict)

    def add(self, element: str) -> None:
        if element not in self.parent:
            self.parent[element] = element
            self.rank[element] = 0

    def find(self, element: str) -> str:
        if element not in self.parent:
            raise Invalid(f"'{element}' was never added; it has no group")
        root = element
        while self.parent[root] != root:
            root = self.parent[root]
        # path compression: point everything on the path at the root
        while self.parent[element] != root:
            self.parent[element], element = root, self.parent[element]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        # union by rank: attach the shorter tree under the taller
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1

    def same_group(self, a: str, b: str) -> bool:
        return self.find(a) == self.find(b)

    def group_count(self) -> str:
        groups = len({self.find(e) for e in self.parent})
        return (
            f"{groups} distinct group(s); one means everything connected, many "
            "a fragmented set, tracked as unions happen without a re-scan"
        )
