from __future__ import annotations

import pytest

from relay.consistenthash import HashRing
from relay.errors import Invalid


class TestMapping:
    def test_a_key_maps_to_some_node(self):
        r = HashRing(vnodes=5)
        r.add("n1")
        r.add("n2")
        assert r.node_for("key-1") in {"n1", "n2"}

    def test_the_same_key_maps_stably(self):
        r = HashRing(vnodes=5)
        r.add("n1")
        r.add("n2")
        assert r.node_for("key-1") == r.node_for("key-1")

    def test_an_empty_ring_is_refused(self):
        with pytest.raises(Invalid):
            HashRing().node_for("k")


class TestMembership:
    def test_a_duplicate_node_is_refused(self):
        r = HashRing()
        r.add("n1")
        with pytest.raises(Invalid) as caught:
            r.add("n1")
        assert "already on the ring" in str(caught.value)

    def test_removing_a_node_reassigns_only_its_keys(self):
        r = HashRing(vnodes=10)
        for n in ("n1", "n2", "n3"):
            r.add(n)
        keys = [f"k{i}" for i in range(200)]
        before = {k: r.node_for(k) for k in keys}
        r.remove("n3")
        # keys that were not on n3 keep their node
        for k in keys:
            if before[k] != "n3":
                assert r.node_for(k) == before[k]


class TestChurn:
    def test_adding_a_node_moves_a_minority_of_keys(self):
        r = HashRing(vnodes=50)
        for n in ("n1", "n2", "n3", "n4"):
            r.add(n)
        keys = [f"k{i}" for i in range(500)]
        note = r.churn(keys, new_node="n5")
        # with 5 nodes, roughly a fifth move; assert well under half
        moved = int(note.split("moved ")[1].split("/")[0])
        assert moved < len(keys) // 2
        assert "one over the node count" in note

    def test_a_bad_vnode_count_is_refused(self):
        with pytest.raises(Invalid):
            HashRing(vnodes=0)
