from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.streamjoin import StreamJoin


class TestCoPartition:
    def test_mismatched_partition_counts_are_refused(self):
        with pytest.raises(Invalid) as caught:
            StreamJoin(window=100, left_partitions=6, right_partitions=3)
        assert "not co-partitioned" in str(caught.value)


class TestJoin:
    def test_a_within_window_match_is_emitted(self):
        j = StreamJoin(window=100, left_partitions=4, right_partitions=4)
        j.arrive_left("k", time=1000)
        matches = j.arrive_right("k", time=1050)
        assert matches == [("k", 1000, 1050)]

    def test_a_match_outside_the_window_is_not_emitted(self):
        j = StreamJoin(window=100, left_partitions=4, right_partitions=4)
        j.arrive_left("k", time=1000)
        matches = j.arrive_right("k", time=1200)
        assert matches == []

    def test_a_different_key_does_not_join(self):
        j = StreamJoin(window=100, left_partitions=4, right_partitions=4)
        j.arrive_left("a", time=1000)
        assert j.arrive_right("b", time=1010) == []

    def test_aged_records_are_dropped_from_state(self):
        j = StreamJoin(window=100, left_partitions=4, right_partitions=4)
        j.arrive_left("k", time=1000)
        # a much later arrival on the right expires the old left record
        j.arrive_right("k", time=5000)
        assert all(t >= 4900 for _, t in j.left_state)


class TestStateNote:
    def test_the_note_reports_held_records(self):
        j = StreamJoin(window=100, left_partitions=4, right_partitions=4)
        j.arrive_left("k", time=1000)
        assert "holds 1 record(s)" in j.state_note()
