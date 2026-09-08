from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.rangeassign import MultiTopicAssignment, range_assign


class TestRangeAssign:
    def test_even_partitions_split_contiguously(self):
        assert range_assign(6, ["c1", "c2"]) == {
            "c1": [0, 1, 2],
            "c2": [3, 4, 5],
        }

    def test_the_remainder_goes_to_the_early_consumers(self):
        assert range_assign(7, ["c1", "c2", "c3"]) == {
            "c1": [0, 1, 2],
            "c2": [3, 4],
            "c3": [5, 6],
        }

    def test_no_consumers_is_refused(self):
        with pytest.raises(Invalid):
            range_assign(6, [])


class TestCoPartitioning:
    def test_aligned_topics_stay_on_one_consumer(self):
        m = MultiTopicAssignment(
            {"orders": 6, "payments": 6}, ["c1", "c2"]
        )
        assert m.co_partitioned("c1", "orders", "payments")
        assert m.co_partitioned("c2", "orders", "payments")

    def test_the_same_partition_number_lands_together(self):
        m = MultiTopicAssignment(
            {"orders": 6, "payments": 6}, ["c1", "c2"]
        )
        assignment = m.assign()
        assert assignment["c1"]["orders"] == assignment["c1"][
            "payments"
        ]


class TestImbalance:
    def test_balanced_topics_report_no_cost(self):
        m = MultiTopicAssignment(
            {"orders": 6, "payments": 6}, ["c1", "c2"]
        )
        assert "cost nothing this time" in m.imbalance_report()

    def test_uneven_topics_state_the_price(self):
        m = MultiTopicAssignment(
            {"orders": 5, "payments": 3}, ["c1", "c2"]
        )
        report = m.imbalance_report()
        assert "spread 3..5 partitions per consumer (gap 2)" in (
            report
        )
        assert "what it paid or is overpaying for" in report
