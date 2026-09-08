from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.hotpartition import HotPartitionDetector


class TestDetect:
    def test_a_dominant_partition_is_hot(self):
        d = HotPartitionDetector(counts={0: 900, 1: 30, 2: 40, 3: 30})
        assert d.hot_partitions() == [0]

    def test_an_even_spread_flags_nothing(self):
        d = HotPartitionDetector(counts={0: 100, 1: 110, 2: 90, 3: 100})
        assert d.hot_partitions() == []

    def test_no_traffic_flags_nothing(self):
        assert HotPartitionDetector().hot_partitions() == []


class TestReport:
    def test_a_hot_partition_names_the_key_fix(self):
        d = HotPartitionDetector(counts={0: 900, 1: 30, 2: 40, 3: 30})
        note = d.report()
        assert "a hot partition from a skewed key" in note
        assert "not more partitions" in note

    def test_a_balanced_topic_reports_ok(self):
        d = HotPartitionDetector(counts={0: 100, 1: 110, 2: 90})
        assert "balanced enough" in d.report()


class TestConfig:
    def test_a_multiple_at_one_is_refused(self):
        with pytest.raises(Invalid):
            HotPartitionDetector(counts={0: 1}, multiple=1.0)
