from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.logtruncation import LogTruncation


class TestTruncate:
    def test_dropping_the_uncommitted_tail_reports_the_count(self):
        t = LogTruncation(log_start=0, high_watermark=80, log_end=100)
        dropped = t.truncate_to(80)
        assert dropped == 20
        assert t.log_end == 80

    def test_truncating_at_the_watermark_keeps_all_committed_records(self):
        t = LogTruncation(log_start=0, high_watermark=80, log_end=100)
        t.truncate_to(90)  # above the watermark
        assert t.log_end == 90
        assert t.uncommitted_tail() == 10

    def test_truncating_at_or_above_the_end_is_a_no_op(self):
        t = LogTruncation(log_start=0, high_watermark=80, log_end=100)
        assert t.truncate_to(100) == 0
        assert t.truncate_to(150) == 0
        assert t.log_end == 100


class TestFloor:
    def test_truncating_below_the_watermark_is_refused(self):
        t = LogTruncation(log_start=0, high_watermark=80, log_end=100)
        with pytest.raises(Invalid) as caught:
            t.truncate_to(70)
        assert "silent data loss" in str(caught.value)

    def test_truncating_below_the_log_start_is_refused(self):
        # start above zero, watermark equal to start, target below start
        t = LogTruncation(log_start=50, high_watermark=50, log_end=100)
        with pytest.raises(Invalid):
            t.truncate_to(40)


class TestInvariant:
    def test_a_watermark_above_the_end_is_refused(self):
        with pytest.raises(Invalid):
            LogTruncation(log_start=0, high_watermark=120, log_end=100)

    def test_a_start_above_the_watermark_is_refused(self):
        with pytest.raises(Invalid):
            LogTruncation(log_start=90, high_watermark=80, log_end=100)


class TestNote:
    def test_the_note_states_the_uncommitted_tail(self):
        t = LogTruncation(log_start=0, high_watermark=80, log_end=100)
        assert "uncommitted tail 20" in t.note()
