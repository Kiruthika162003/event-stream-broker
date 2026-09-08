from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.repartition import Repartitioner


class TestPartitionFor:
    def test_the_same_key_always_routes_to_one_partition(self):
        r = Repartitioner(partitions=8)
        first = r.partition_for("india")
        second = r.partition_for("india")
        assert first == second
        assert 0 <= first < 8

    def test_a_zero_partition_topic_is_refused(self):
        with pytest.raises(Invalid):
            Repartitioner(partitions=0)


class TestGroupingSafe:
    def test_a_consistently_routed_key_is_safe_to_group(self):
        r = Repartitioner(partitions=8)
        r.partition_for("india")
        r.partition_for("india")
        assert r.is_grouping_safe("india")
        r.require_grouping_safe("india")

    def test_a_key_spread_across_partitions_is_unsafe(self):
        r = Repartitioner(partitions=8)
        # simulate a mis-partitioned key by injecting two targets
        r.routed["bad"] = {1, 4}
        assert not r.is_grouping_safe("bad")
        with pytest.raises(Invalid) as caught:
            r.require_grouping_safe("bad")
        assert "partial totals" in str(caught.value)


class TestShuffleCost:
    def test_it_reports_the_fraction_moved(self):
        r = Repartitioner(partitions=8)
        note = r.shuffle_cost(changed=80, total=100)
        assert "80/100 record(s) changed partition (80%)" in note
        assert "doubling the traffic" in note

    def test_no_records_no_shuffle(self):
        r = Repartitioner(partitions=8)
        assert "no shuffle" in r.shuffle_cost(0, 0)
