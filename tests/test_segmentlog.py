from __future__ import annotations

import pytest

from relay.errors import Lagging, Missing, Sealed
from relay.records import Record
from relay.segmentlog import Segment, SegmentLog


def filled_log(count: int, size: int = 500) -> SegmentLog:
    log = SegmentLog()
    for number in range(count):
        log.append(
            Record(value=f"event-{number:04}".encode() + b"x" * size)
        )
    return log


class TestAppending:
    def test_offsets_are_dense_and_monotonic(self):
        log = SegmentLog()
        offsets = [
            log.append(Record(value=b"v")) for _ in range(5)
        ]
        assert offsets == [0, 1, 2, 3, 4]

    def test_the_log_rolls_at_the_threshold(self):
        log = filled_log(12)
        assert log.rolls >= 1
        assert log.segments[0].sealed

    def test_a_sealed_segment_refuses_appends(self):
        segment = Segment(base_offset=0, sealed=True)
        with pytest.raises(Sealed) as caught:
            segment.append(Record(value=b"v"))
        assert "immutability is the product" in str(caught.value)


class TestReading:
    def test_reads_address_offsets_across_segments(self):
        log = filled_log(12)
        assert log.read(0).value.startswith(b"event-0000")
        assert log.read(11).value.startswith(b"event-0011")

    def test_the_future_offset_is_missing(self):
        log = filled_log(3)
        with pytest.raises(Missing) as caught:
            log.read(99)
        assert "the log ends at 2" in str(caught.value)

    def test_falling_off_the_window_is_lagging_not_empty(self):
        log = filled_log(20)
        log.drop_sealed_before(log.segments[1].base_offset)
        with pytest.raises(Lagging) as caught:
            log.read(0)
        assert "the log now starts at" in str(caught.value)
        assert "beats a silent empty result" in str(caught.value)


class TestRetentionMechanics:
    def test_only_whole_sealed_segments_drop(self):
        log = filled_log(20)
        first_kept = log.segments[1].base_offset
        dropped = log.drop_sealed_before(first_kept)
        assert dropped == 1
        assert log.first_offset() == first_kept

    def test_the_active_segment_never_drops(self):
        log = filled_log(3)
        assert log.drop_sealed_before(999) == 0

    def test_the_shape_reads_like_a_sentence(self):
        shape = filled_log(12).shape()
        assert "sealed" in shape
        assert "roll(s)" in shape
