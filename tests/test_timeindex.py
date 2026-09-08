from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.timeindex import TimeIndex


def filled() -> TimeIndex:
    idx = TimeIndex(interval=10)
    for offset in range(100):
        idx.on_append(receive_time=1000 + offset * 5, offset=offset)
    return idx


class TestSparseness:
    def test_one_entry_per_interval(self):
        assert len(filled().entries) == 10

    def test_a_bad_interval_is_refused(self):
        with pytest.raises(Invalid):
            TimeIndex(interval=0)


class TestSeeking:
    def test_a_mid_stream_time_finds_the_offset(self):
        offset, note = filled().offset_for_time(1225)
        assert offset == 50
        assert "broker receive time, not producer event time" in (
            note
        )

    def test_a_time_before_the_start_returns_log_start(self):
        offset, note = filled().offset_for_time(500)
        assert offset == 0
        assert "returning the log start" in note

    def test_a_time_after_the_end_returns_log_end(self):
        offset, note = filled().offset_for_time(99999)
        assert offset == 100
        assert "returning the log end" in note

    def test_an_empty_index_cannot_seek(self):
        with pytest.raises(Invalid):
            TimeIndex(interval=10).offset_for_time(1)


class TestHonesty:
    def test_the_ingest_delay_caveat_is_stated(self):
        _, note = filled().offset_for_time(1225)
        assert "off by the ingest delay" in note
