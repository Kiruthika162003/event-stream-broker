from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.merkletree import MerkleTree


class TestRoot:
    def test_identical_leaves_give_the_same_root(self):
        a = MerkleTree(leaves=["r1", "r2", "r3", "r4"])
        b = MerkleTree(leaves=["r1", "r2", "r3", "r4"])
        assert a.root() == b.root()

    def test_a_changed_leaf_changes_the_root(self):
        a = MerkleTree(leaves=["r1", "r2", "r3", "r4"])
        b = MerkleTree(leaves=["r1", "X", "r3", "r4"])
        assert a.root() != b.root()


class TestDiff:
    def test_matching_trees_diff_to_nothing(self):
        a = MerkleTree(leaves=["r1", "r2", "r3"])
        b = MerkleTree(leaves=["r1", "r2", "r3"])
        assert a.diff(b) == []

    def test_diff_finds_the_changed_leaves(self):
        a = MerkleTree(leaves=["r1", "r2", "r3", "r4"])
        b = MerkleTree(leaves=["r1", "X", "r3", "Y"])
        assert a.diff(b) == [1, 3]

    def test_different_leaf_counts_are_refused(self):
        a = MerkleTree(leaves=["r1", "r2"])
        b = MerkleTree(leaves=["r1", "r2", "r3"])
        with pytest.raises(Invalid) as caught:
            a.diff(b)
        assert "do not line up" in str(caught.value)


class TestDivergence:
    def test_agreement_is_one_hash(self):
        a = MerkleTree(leaves=["r1", "r2"])
        b = MerkleTree(leaves=["r1", "r2"])
        assert "one hash compared" in a.divergence(b)

    def test_localized_divergence_sends_only_differences(self):
        a = MerkleTree(leaves=["r1", "r2", "r3", "r4"])
        b = MerkleTree(leaves=["r1", "X", "r3", "r4"])
        assert "send only the differing records" in a.divergence(b)

    def test_wide_divergence_prefers_a_full_transfer(self):
        a = MerkleTree(leaves=["a", "b", "c", "d"])
        b = MerkleTree(leaves=["w", "x", "y", "z"])
        assert "full transfer beats the tree" in a.divergence(b)
