from __future__ import annotations

import pytest

from relay.errors import Invalid, Missing
from relay.offsetindex import OffsetIndex


class TestAdd:
    def test_entries_accumulate(self):
        idx = OffsetIndex(base_offset=0)
        idx.add(0, 0)
        idx.add(10, 4096)
        assert len(idx.entries) == 2

    def test_an_offset_below_base_is_refused(self):
        idx = OffsetIndex(base_offset=100)
        with pytest.raises(Invalid) as caught:
            idx.add(50, 0)
        assert "below the segment base" in str(caught.value)

    def test_a_non_increasing_entry_is_refused(self):
        idx = OffsetIndex(base_offset=0)
        idx.add(10, 4096)
        with pytest.raises(Invalid) as caught:
            idx.add(10, 8192)
        assert "strictly increasing" in str(caught.value)


class TestFloorPosition:
    def test_the_floor_is_the_largest_offset_not_past_target(self):
        idx = OffsetIndex(base_offset=0)
        idx.add(0, 0)
        idx.add(10, 4096)
        idx.add(20, 8192)
        assert idx.floor_position(15) == 4096

    def test_an_exact_hit_returns_that_position(self):
        idx = OffsetIndex(base_offset=0)
        idx.add(0, 0)
        idx.add(10, 4096)
        idx.add(20, 8192)
        assert idx.floor_position(20) == 8192

    def test_an_empty_index_returns_the_segment_start(self):
        idx = OffsetIndex(base_offset=0)
        assert idx.floor_position(5) == 0

    def test_an_offset_before_base_looks_elsewhere(self):
        idx = OffsetIndex(base_offset=100)
        with pytest.raises(Missing) as caught:
            idx.floor_position(50)
        assert "earlier segment" in str(caught.value)


class TestAverageScan:
    def test_the_scan_distance_follows_the_interval(self):
        idx = OffsetIndex(base_offset=0, interval_bytes=4096)
        note = idx.average_scan(record_bytes=512)
        assert "~8 record(s)" in note
        assert "long scan the index was to prevent" in note
