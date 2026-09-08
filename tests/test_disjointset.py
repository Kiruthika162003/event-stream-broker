from __future__ import annotations

import pytest

from relay.disjointset import DisjointSet
from relay.errors import Invalid


def _set(*elements):
    d = DisjointSet()
    for e in elements:
        d.add(e)
    return d


class TestUnionFind:
    def test_unioned_elements_share_a_group(self):
        d = _set("a", "b", "c")
        d.union("a", "b")
        assert d.same_group("a", "b")
        assert not d.same_group("a", "c")

    def test_union_is_transitive(self):
        d = _set("a", "b", "c")
        d.union("a", "b")
        d.union("b", "c")
        assert d.same_group("a", "c")

    def test_find_of_an_unknown_element_is_refused(self):
        d = _set("a")
        with pytest.raises(Invalid):
            d.find("z")


class TestGroupCount:
    def test_it_counts_distinct_groups(self):
        d = _set("a", "b", "c", "d")
        d.union("a", "b")
        d.union("c", "d")
        assert "2 distinct group(s)" in d.group_count()

    def test_merging_all_collapses_to_one(self):
        d = _set("a", "b", "c")
        d.union("a", "b")
        d.union("b", "c")
        assert "1 distinct group(s)" in d.group_count()


class TestPathCompression:
    def test_find_flattens_the_tree(self):
        d = _set("a", "b", "c", "d")
        d.union("a", "b")
        d.union("b", "c")
        d.union("c", "d")
        root = d.find("d")
        # after find, d points directly at the root
        assert d.parent["d"] == root
