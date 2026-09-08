from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.logstartoffset import LogStartOffset


class TestAdvance:
    def test_advancing_the_start_reports_the_deleted_count(self):
        lso = LogStartOffset(log_start=0, high_watermark=100, log_end=100)
        deleted = lso.advance_start(30)
        assert deleted == 30
        assert lso.log_start == 30

    def test_moving_the_start_backward_is_refused(self):
        lso = LogStartOffset(log_start=50, high_watermark=100, log_end=100)
        with pytest.raises(Invalid) as caught:
            lso.advance_start(40)
        assert "restore deleted records" in str(caught.value)

    def test_moving_the_start_past_the_watermark_is_refused(self):
        lso = LogStartOffset(log_start=0, high_watermark=60, log_end=100)
        with pytest.raises(Invalid) as caught:
            lso.advance_start(80)
        assert "not yet consumed" in str(caught.value)


class TestFetch:
    def test_an_offset_at_or_above_the_start_is_fetchable(self):
        lso = LogStartOffset(log_start=30, high_watermark=100, log_end=100)
        assert lso.is_fetchable(30)
        assert lso.is_fetchable(100)

    def test_an_offset_below_the_start_is_out_of_range(self):
        lso = LogStartOffset(log_start=30, high_watermark=100, log_end=100)
        assert not lso.is_fetchable(10)
        with pytest.raises(Invalid) as caught:
            lso.check_fetch(10)
        assert "out-of-range" in str(caught.value)

    def test_an_offset_past_the_end_is_refused(self):
        lso = LogStartOffset(log_start=0, high_watermark=100, log_end=100)
        with pytest.raises(Invalid):
            lso.check_fetch(200)


class TestInvariant:
    def test_a_start_above_the_watermark_is_refused_at_construction(self):
        with pytest.raises(Invalid):
            LogStartOffset(log_start=80, high_watermark=60, log_end=100)


class TestNote:
    def test_the_note_states_the_aged_out_count(self):
        lso = LogStartOffset(log_start=30, high_watermark=100, log_end=100)
        assert "30 record(s) aged out" in lso.note()
