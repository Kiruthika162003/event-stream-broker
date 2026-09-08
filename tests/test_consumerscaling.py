from __future__ import annotations

import pytest

from relay.consumerscaling import ConsumerScaling
from relay.errors import Invalid


class TestActiveIdle:
    def test_consumers_under_partitions_are_all_active(self):
        s = ConsumerScaling(partitions=8, consumers=4)
        assert s.active() == 4
        assert s.idle() == 0

    def test_consumers_over_partitions_leave_idle_ones(self):
        s = ConsumerScaling(partitions=4, consumers=6)
        assert s.active() == 4
        assert s.idle() == 2

    def test_max_useful_is_the_partition_count(self):
        assert ConsumerScaling(partitions=8, consumers=100).max_useful() == 8


class TestReport:
    def test_room_to_grow_is_reported(self):
        s = ConsumerScaling(partitions=8, consumers=4)
        assert "room for 4 more" in s.report()

    def test_fully_parallel_is_reported(self):
        s = ConsumerScaling(partitions=4, consumers=4)
        assert "fully parallel" in s.report()

    def test_idle_consumers_point_at_more_partitions(self):
        s = ConsumerScaling(partitions=4, consumers=6)
        note = s.report()
        assert "2 idle" in note
        assert "add" in note
        assert "partitions, not consumers" in note


class TestConfig:
    def test_zero_partitions_is_refused(self):
        with pytest.raises(Invalid):
            ConsumerScaling(partitions=0, consumers=1)
