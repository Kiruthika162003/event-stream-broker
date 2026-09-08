from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.orset import ORSet


class TestAddRemove:
    def test_add_then_contains(self):
        s = ORSet()
        s.add("x")
        assert s.contains("x")

    def test_remove_takes_it_out(self):
        s = ORSet()
        s.add("x")
        s.remove("x")
        assert not s.contains("x")

    def test_removing_an_absent_element_is_refused(self):
        s = ORSet()
        with pytest.raises(Invalid):
            s.remove("x")


class TestConcurrentAddWins:
    def test_a_concurrent_add_survives_a_remove(self):
        # replica a removes x; replica b concurrently adds x again
        a = ORSet(node_id="a")
        a.add("x")
        b = ORSet(node_id="b")
        b.merge(a)  # both know the first add
        a.remove("x")  # a removes the observed tag
        b.add("x")  # b adds a new tag a's remove never saw
        a.merge(b)
        # add wins: x is still present
        assert a.contains("x")


class TestMerge:
    def test_merge_unions_adds_and_removes(self):
        a = ORSet(node_id="a")
        a.add("x")
        b = ORSet(node_id="b")
        b.add("y")
        a.merge(b)
        assert a.elements() == {"x", "y"}

    def test_merge_is_convergent_both_ways(self):
        a = ORSet(node_id="a")
        a.add("x")
        b = ORSet(node_id="b")
        b.add("y")
        b.remove("y")
        a.merge(b)
        b.merge(a)
        assert a.elements() == b.elements() == {"x"}


class TestOverhead:
    def test_tag_overhead_is_reported(self):
        s = ORSet()
        s.add("x")
        s.add("x")
        assert "2 add-tag(s) for 1 live element(s)" in s.tag_overhead()
