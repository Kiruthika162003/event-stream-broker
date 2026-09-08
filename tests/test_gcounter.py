from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.gcounter import GCounter


class TestIncrement:
    def test_a_node_increments_its_own_entry(self):
        c = GCounter(node_id="a")
        c.increment()
        c.increment(3)
        assert c.value() == 4
        assert c.entries == {"a": 4}

    def test_a_non_positive_increment_is_refused(self):
        with pytest.raises(Invalid):
            GCounter(node_id="a").increment(0)


class TestMerge:
    def test_merge_takes_the_max_per_entry(self):
        a = GCounter(node_id="a", entries={"a": 5, "b": 2})
        a.merge({"a": 3, "b": 7, "c": 1})
        assert a.entries == {"a": 5, "b": 7, "c": 1}
        assert a.value() == 13

    def test_merge_is_order_independent(self):
        a = GCounter(node_id="a", entries={"a": 3})
        b = GCounter(node_id="b", entries={"b": 4})
        x = GCounter(node_id="x")
        x.merge(a.entries)
        x.merge(b.entries)
        y = GCounter(node_id="y")
        y.merge(b.entries)
        y.merge(a.entries)
        assert x.value() == y.value() == 7

    def test_merge_is_idempotent(self):
        a = GCounter(node_id="a", entries={"a": 3})
        x = GCounter(node_id="x")
        x.merge(a.entries)
        x.merge(a.entries)  # same update twice
        assert x.value() == 3


class TestReport:
    def test_report_states_the_value(self):
        c = GCounter(node_id="a")
        c.increment(5)
        assert "value 5" in c.report()
