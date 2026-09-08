from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.sessionwindow import SessionWindows


class TestSessions:
    def test_close_records_form_one_session(self):
        w = SessionWindows(gap=10)
        w.add(0)
        w.add(5)
        w.add(8)
        assert w.session_bounds() == [(0, 8)]

    def test_a_gap_starts_a_new_session(self):
        w = SessionWindows(gap=10)
        w.add(0)
        w.add(5)
        w.add(100)
        assert w.session_bounds() == [(0, 5), (100, 100)]

    def test_a_bridging_record_merges_two_sessions(self):
        w = SessionWindows(gap=10)
        w.add(0)
        w.add(5)
        w.add(20)
        w.add(25)
        # two sessions (0-5) and (20-25); a record at 13 bridges both
        assert len(w.session_bounds()) == 2
        w.add(13)
        assert w.session_bounds() == [(0, 25)]


class TestConfig:
    def test_a_non_positive_gap_is_refused(self):
        with pytest.raises(Invalid):
            SessionWindows(gap=0)


class TestReport:
    def test_the_report_counts_sessions(self):
        w = SessionWindows(gap=10)
        for t in (0, 5, 100, 105):
            w.add(t)
        note = w.report(record_count=4)
        assert "4 record(s) collapsed into 2 session(s)" in note
