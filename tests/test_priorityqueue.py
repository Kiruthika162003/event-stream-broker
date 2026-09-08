from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.priorityqueue import PriorityQueue


class TestOrder:
    def test_pop_returns_the_minimum_first(self):
        q = PriorityQueue()
        for p, item in [(5, "e"), (1, "a"), (3, "c"), (2, "b")]:
            q.push(p, item)
        assert q.pop() == (1, "a")
        assert q.pop() == (2, "b")

    def test_it_pops_in_sorted_order(self):
        q = PriorityQueue()
        priorities = [9, 3, 7, 1, 8, 2, 6, 5, 4]
        for p in priorities:
            q.push(p, f"item{p}")
        got = [q.pop()[0] for _ in priorities]
        assert got == sorted(priorities)

    def test_peek_does_not_remove(self):
        q = PriorityQueue()
        q.push(5, "e")
        q.push(1, "a")
        assert q.peek() == (1, "a")
        assert q.peek() == (1, "a")


class TestEmpty:
    def test_pop_of_empty_is_refused(self):
        with pytest.raises(Invalid):
            PriorityQueue().pop()

    def test_peek_of_empty_is_refused(self):
        with pytest.raises(Invalid):
            PriorityQueue().peek()


class TestSize:
    def test_size_reports_the_backlog(self):
        q = PriorityQueue()
        q.push(1, "a")
        q.push(2, "b")
        assert "2 item(s) queued" in q.size()
