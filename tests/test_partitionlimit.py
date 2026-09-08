from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.partitionlimit import PartitionLimit


class TestCreate:
    def test_topics_within_the_cap_are_created(self):
        pl = PartitionLimit(cap=100)
        pl.create("a", 30)
        assert "total 70/100" in pl.create("b", 40)

    def test_a_topic_over_the_cap_is_refused(self):
        pl = PartitionLimit(cap=50)
        pl.create("a", 40)
        with pytest.raises(Invalid) as caught:
            pl.create("b", 20)
        assert "not the disk's" in str(caught.value)

    def test_a_duplicate_topic_is_refused(self):
        pl = PartitionLimit(cap=100)
        pl.create("a", 10)
        with pytest.raises(Invalid):
            pl.create("a", 10)

    def test_a_zero_partition_topic_is_refused(self):
        pl = PartitionLimit(cap=100)
        with pytest.raises(Invalid):
            pl.create("a", 0)


class TestConfig:
    def test_a_zero_cap_is_refused(self):
        with pytest.raises(Invalid):
            PartitionLimit(cap=0)


class TestHeadroom:
    def test_headroom_reports_the_remaining(self):
        pl = PartitionLimit(cap=100)
        pl.create("a", 70)
        assert "30 partition(s) of headroom" in pl.headroom()
