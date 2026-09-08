from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.orderingscope import OrderingScope


class TestOrdered:
    def test_the_same_key_is_always_ordered_with_itself(self):
        s = OrderingScope(partitions=8)
        assert s.ordered_between("cust-1", "cust-1")

    def test_a_single_partition_orders_every_key(self):
        s = OrderingScope(partitions=1)
        assert s.ordered_between("a", "b")

    def test_a_zero_partition_topic_is_refused(self):
        with pytest.raises(Invalid):
            OrderingScope(partitions=0)


class TestOrderNote:
    def test_same_partition_keys_are_guaranteed(self):
        s = OrderingScope(partitions=1)
        assert "order is guaranteed" in s.order_note("a", "b")

    def test_cross_partition_keys_have_no_order(self):
        s = OrderingScope(partitions=1000)
        # find two keys that hash to different partitions
        a, b = "alpha", "beta"
        if s.partition_for(a) == s.partition_for(b):
            b = "gamma"
        note = s.order_note(a, b)
        assert "no" in note
        assert "order between them" in note


class TestSpread:
    def test_one_partition_names_the_bottleneck(self):
        s = OrderingScope(partitions=1)
        assert "serializes all throughput" in s.spread(["a", "b", "c"])

    def test_many_partitions_report_the_spread(self):
        s = OrderingScope(partitions=8)
        note = s.spread(["a", "b", "c", "d"])
        assert "4 key(s) spread across" in note
