from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.rendezvoushash import RendezvousHash


def _hash():
    r = RendezvousHash()
    for n in ("n1", "n2", "n3"):
        r.add(n)
    return r


class TestPlace:
    def test_a_key_places_on_some_node(self):
        r = _hash()
        assert r.place("key-1") in {"n1", "n2", "n3"}

    def test_placement_is_stable(self):
        r = _hash()
        assert r.place("key-1") == r.place("key-1")

    def test_placing_with_no_nodes_is_refused(self):
        with pytest.raises(Invalid):
            RendezvousHash().place("k")


class TestRanked:
    def test_ranked_lists_all_nodes_best_first(self):
        r = _hash()
        ranked = r.ranked("key-1")
        assert len(ranked) == 3
        assert ranked[0] == r.place("key-1")

    def test_the_second_choice_is_the_failover_target(self):
        r = _hash()
        ranked = r.ranked("key-1")
        r.remove(ranked[0])
        assert r.place("key-1") == ranked[1]


class TestChurn:
    def test_adding_a_node_moves_a_minority_of_keys(self):
        r = _hash()
        keys = [f"k{i}" for i in range(300)]
        note = r.moved_if_added(keys, new_node="n4")
        moved = int(note.split("moves ")[1].split("/")[0])
        assert moved < len(keys) // 2
        assert "minimal-disruption promise" in note
