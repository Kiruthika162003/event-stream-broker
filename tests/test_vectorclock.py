from __future__ import annotations

from relay.vectorclock import AFTER, BEFORE, CONCURRENT, EQUAL, VectorClock


class TestTickMerge:
    def test_tick_increments_own_entry(self):
        c = VectorClock(node_id="a")
        c.tick()
        c.tick()
        assert c.vector == {"a": 2}

    def test_merge_takes_element_wise_max_then_increments(self):
        c = VectorClock(node_id="a", vector={"a": 1})
        c.merge({"a": 1, "b": 5})
        assert c.vector == {"a": 2, "b": 5}


class TestCompare:
    def test_before_when_dominated(self):
        assert VectorClock.compare({"a": 1, "b": 1}, {"a": 2, "b": 1}) == BEFORE

    def test_after_when_dominating(self):
        assert VectorClock.compare({"a": 3, "b": 1}, {"a": 2, "b": 1}) == AFTER

    def test_equal_when_identical(self):
        assert VectorClock.compare({"a": 2}, {"a": 2}) == EQUAL

    def test_concurrent_when_neither_dominates(self):
        assert VectorClock.compare({"a": 2, "b": 1}, {"a": 1, "b": 2}) == CONCURRENT

    def test_missing_entries_count_as_zero(self):
        assert VectorClock.compare({"a": 1}, {"b": 1}) == CONCURRENT


class TestConflict:
    def test_concurrent_updates_are_a_conflict(self):
        assert VectorClock.conflict({"a": 2, "b": 1}, {"a": 1, "b": 2})

    def test_ordered_updates_are_not_a_conflict(self):
        assert not VectorClock.conflict({"a": 1}, {"a": 2})
