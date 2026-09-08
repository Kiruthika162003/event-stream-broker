from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.urp import PartitionReplication, ReplicationMonitor


def healthy() -> PartitionReplication:
    return PartitionReplication(0, replication_factor=3, in_sync=3, min_in_sync=2)


def at_risk() -> PartitionReplication:
    return PartitionReplication(1, replication_factor=3, in_sync=2, min_in_sync=2)


def under_min() -> PartitionReplication:
    return PartitionReplication(2, replication_factor=3, in_sync=1, min_in_sync=2)


class TestStates:
    def test_a_healthy_partition_has_margin(self):
        assert healthy().state() == "healthy"
        assert healthy().margin() == 1

    def test_at_the_minimum_is_at_risk(self):
        assert at_risk().state() == "at-risk"
        assert at_risk().margin() == 0

    def test_below_the_minimum_is_under_minimum(self):
        assert under_min().state() == "under-minimum"

    def test_in_sync_above_factor_is_impossible(self):
        with pytest.raises(Invalid):
            PartitionReplication(0, 3, in_sync=5, min_in_sync=2)


class TestTheMonitor:
    def test_under_replicated_counts_below_factor(self):
        monitor = ReplicationMonitor(
            [healthy(), at_risk(), under_min()]
        )
        assert len(monitor.under_replicated()) == 2

    def test_at_risk_or_worse_lists_the_exposed(self):
        monitor = ReplicationMonitor(
            [healthy(), at_risk(), under_min()]
        )
        assert monitor.at_risk_or_worse() == [1, 2]

    def test_the_blast_radius_is_never_averaged(self):
        monitor = ReplicationMonitor(
            [healthy(), healthy(), under_min()]
        )
        report = monitor.blast_radius()
        assert "1 partition(s) at risk or worse" in report
        assert "worst margin -1" in report
        assert "never averaged away" in report

    def test_a_fully_healthy_cluster_says_so(self):
        monitor = ReplicationMonitor([healthy(), healthy()])
        assert "no data-loss exposure" in monitor.blast_radius()

    def test_an_empty_monitor_is_refused(self):
        with pytest.raises(Invalid):
            ReplicationMonitor([]).blast_radius()
