from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.skiplist import SkipList


def _never():
    return False


def _alternating():
    state = {"n": 0}

    def coin():
        state["n"] += 1
        return state["n"] % 2 == 0

    return coin


class TestSearch:
    def test_a_flat_list_searches_correctly(self):
        s = SkipList(coin=_never)
        for v in (5, 3, 8, 1, 9):
            s.insert(v)
        assert s.search(3)
        assert not s.search(4)
        assert s.in_order() == [1, 3, 5, 8, 9]

    def test_a_multi_level_list_searches_correctly(self):
        s = SkipList(coin=_alternating())
        for v in (5, 3, 8, 1, 9, 2, 7):
            s.insert(v)
        for v in (1, 2, 3, 5, 7, 8, 9):
            assert s.search(v)
        assert not s.search(6)
        assert s.in_order() == [1, 2, 3, 5, 7, 8, 9]

    def test_a_search_on_empty_is_false(self):
        assert not SkipList(coin=_never).search(1)


class TestInsert:
    def test_duplicates_are_not_inserted_twice(self):
        s = SkipList(coin=_never)
        s.insert(5)
        s.insert(5)
        assert s.in_order() == [5]

    def test_insertion_keeps_order_regardless_of_arrival(self):
        s = SkipList(coin=_alternating())
        for v in (9, 1, 5, 3, 7):
            s.insert(v)
        assert s.in_order() == [1, 3, 5, 7, 9]


class TestLevels:
    def test_level_counts_reports(self):
        s = SkipList(coin=_alternating())
        for v in range(10):
            s.insert(v)
        assert "per-level counts" in s.level_counts()

    def test_an_empty_list_has_no_levels(self):
        with pytest.raises(Invalid):
            SkipList(coin=_never).level_counts()
