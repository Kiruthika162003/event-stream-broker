from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.partitioner import (
    RoundRobinPartitioner,
    StickyPartitioner,
    compare_strategies,
    count_batches_roundrobin,
)


class TestRoundRobin:
    def test_it_cycles_through_partitions(self):
        p = RoundRobinPartitioner(3)
        assert [p.assign() for _ in range(4)] == [0, 1, 2, 0]

    def test_zero_partitions_is_refused(self):
        with pytest.raises(Invalid):
            RoundRobinPartitioner(0)


class TestSticky:
    def test_it_fills_a_partition_before_moving_on(self):
        p = StickyPartitioner(partitions=3, batch_size=2)
        assert [p.assign() for _ in range(4)] == [0, 0, 1, 1]

    def test_it_counts_the_batches_it_forms(self):
        p = StickyPartitioner(partitions=3, batch_size=2)
        for _ in range(6):
            p.assign()
        assert p.batches_produced == 3

    def test_a_bad_configuration_is_refused(self):
        with pytest.raises(Invalid):
            StickyPartitioner(partitions=1, batch_size=0)


class TestTheComparison:
    def test_sticky_sends_fewer_batches(self):
        rr = count_batches_roundrobin(100, 10, 16)
        sticky = StickyPartitioner(10, 16)
        for _ in range(100):
            sticky.assign()
        assert sticky.batches_produced < rr

    def test_the_comparison_states_both_counts(self):
        report = compare_strategies(100, 10, 16)
        assert "round-robin sends 10 batches, sticky sends 7" in (
            report
        )
        assert "the round-robin intuition gets wrong" in report
