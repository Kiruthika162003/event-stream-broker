"""Merkle tree: compare two replicas by hashes, descending only where they differ.

Reconciling two replicas that should hold the same data, an anti-
entropy pass between a leader and a follower, or between two
mirrored clusters, could compare every record, which costs the
whole dataset even when almost all of it agrees. A Merkle tree
makes the comparison cost proportional to the difference, not the
data. Each leaf is the hash of a record or a small block, each
internal node is the hash of its children, and the root is a hash
of everything, so if two replicas' roots match, all their data
matches and the comparison is one hash. If the roots differ, the
data differs somewhere, and descending into the children whose
hashes disagree, skipping the subtrees whose hashes match, finds
exactly the differing leaves in a logarithmic number of hash
comparisons per difference, so reconciling replicas that differ in
a few records transfers a few hashes and those records rather than
everything. This is why Merkle trees back replica repair: the tree
localizes the difference cheaply, and only the differing records are
sent. The tree hashes the leaves, folds them pairwise up to the
root, and a diff of two trees over the same leaf count descends
from the root collecting the leaf indices whose hashes differ. It
refuses to diff trees of different leaf counts, because their leaves
do not line up and comparing them would report differences that are
really misalignment, and it reports the fraction of leaves that
differ, because a diff touching most leaves is two replicas that
have diverged widely, where a full transfer beats the tree's
per-difference cost, the case the tree does not help."
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from relay.errors import Invalid


def _h(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class MerkleTree:
    leaves: list[str] = field(default_factory=list)

    def leaf_hashes(self) -> list[str]:
        return [_h(leaf) for leaf in self.leaves]

    def root(self) -> str:
        level = self.leaf_hashes()
        if not level:
            return _h("")
        while len(level) > 1:
            nxt = []
            for i in range(0, len(level), 2):
                pair = level[i] + (level[i + 1] if i + 1 < len(level) else level[i])
                nxt.append(_h(pair))
            level = nxt
        return level[0]

    def diff(self, other: MerkleTree) -> list[int]:
        if len(self.leaves) != len(other.leaves):
            raise Invalid(
                "trees have different leaf counts; their leaves do not line "
                "up and a diff would report misalignment as difference"
            )
        if self.root() == other.root():
            return []
        a, b = self.leaf_hashes(), other.leaf_hashes()
        return [i for i in range(len(a)) if a[i] != b[i]]

    def divergence(self, other: MerkleTree) -> str:
        differing = self.diff(other)
        total = len(self.leaves)
        if not differing:
            return "roots match; replicas agree, one hash compared"
        pct = len(differing) / total * 100
        note = f"{len(differing)}/{total} leaves differ ({pct:.0f}%)"
        if pct > 50:
            return note + "; widely diverged, a full transfer beats the tree here"
        return note + "; localized, send only the differing records"
