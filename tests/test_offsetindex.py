from __future__ import annotations

import pytest

from relay.errors import Invalid, Missing
from relay.offsetindex import OffsetIndex


def filled_index(count: int = 100, interval: int = 10) -> OffsetIndex:
    index = OffsetIndex(base_offset=0, interval=interval)
    position = 0
    for offset in range(count):
        index.on_append(offset, position)
        position += 50
    return index


class TestSparseness:
    def test_one_entry_per_interval(self):
        index = filled_index(100, 10)
        assert len(index.entries) == 10

    def test_a_bad_interval_is_refused(self):
        with pytest.raises(Invalid):
            OffsetIndex(base_offset=0, interval=0)


class TestSeeking:
    def test_seek_lands_on_the_nearest_indexed_offset(self):
        index = filled_index(100, 10)
        position, scan = index.seek(42)
        assert position == 40 * 50
        assert scan == 2

    def test_the_scan_is_bounded_by_the_interval(self):
        index = filled_index(100, 10)
        for target in range(100):
            _, scan = index.seek(target)
            assert scan <= index.scan_bound()

    def test_an_offset_below_the_index_is_missing(self):
        index = OffsetIndex(base_offset=50, interval=10)
        index.on_append(50, 0)
        with pytest.raises(Missing):
            index.seek(10)

    def test_an_empty_index_cannot_seek(self):
        with pytest.raises(Missing):
            OffsetIndex(base_offset=0, interval=10).seek(0)


class TestRebuild:
    def test_the_index_rebuilds_from_the_log(self):
        original = filled_index(100, 10)
        records = [
            (offset, offset * 50) for offset in range(100)
        ]
        rebuilt = OffsetIndex(base_offset=0, interval=10)
        rebuilt.rebuild_from(records)
        assert rebuilt.entries == original.entries


class TestTheReport:
    def test_the_report_names_the_knob(self):
        report = filled_index(100, 10).report()
        assert "worst-case scan 9 record(s)" in report
        assert "seek latency and index size" in report
