from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.groupdescribe import GroupDescription, PartitionStatus


def description(stable: bool = True) -> GroupDescription:
    return GroupDescription(
        group="billing",
        stable=stable,
        partitions=[
            PartitionStatus(0, "c1", committed=1000, end_offset=1005),
            PartitionStatus(7, "c3", committed=1000, end_offset=41000),
            PartitionStatus(3, None, committed=500, end_offset=9000),
        ],
    )


class TestWorstFirst:
    def test_the_most_lagging_partition_sorts_first(self):
        rows = description().worst_first()
        assert rows[0].partition == 7
        assert rows[0].lag() == 40000

    def test_the_describe_names_symptom_and_suspect(self):
        report = description().describe()
        assert "partition 7: c3" in report
        assert "lag 40000" in report

    def test_a_healthy_partition_reads_current(self):
        report = description().describe()
        assert "partition 0: c1" in report
        assert "lag 5" in report


class TestUnowned:
    def test_an_unowned_partition_is_surfaced(self):
        assert description().unowned() == [3]

    def test_the_unowned_warning_names_the_real_cause(self):
        report = description().describe()
        assert "UNOWNED [3]" in report
        assert "a member died without reassignment" in report


class TestStability:
    def test_a_mid_rebalance_describe_is_refused(self):
        with pytest.raises(Invalid) as caught:
            description(stable=False).describe()
        assert "wrong the instant it prints" in str(caught.value)
