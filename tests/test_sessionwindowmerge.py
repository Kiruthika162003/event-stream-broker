from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.sessionwindowmerge import SessionWindowMerge


class TestSeparateSessions:
    def test_events_within_the_gap_form_one_session(self):
        s = SessionWindowMerge(gap=10)
        s.add_event(0)
        s.add_event(5)
        s.add_event(8)
        assert s.spans() == [(0, 8, 3)]

    def test_events_beyond_the_gap_stay_separate(self):
        s = SessionWindowMerge(gap=10)
        s.add_event(0)
        s.add_event(100)
        assert len(s.spans()) == 2


class TestMerge:
    def test_a_bridging_event_fuses_two_sessions(self):
        s = SessionWindowMerge(gap=10)
        s.add_event(0)  # session A: [0,0]
        s.add_event(30)  # session B: [30,30], 30 apart so separate
        assert len(s.spans()) == 2
        # a late event at 18 is within a gap of both A (end 0, +10=10... not 18)
        # use 15: within gap of A? 0+10=10 < 15 no. Need event bridging both.
        s.add_event(8)  # extends A to [0,8]
        s.add_event(24)  # extends B to [24,30]? 30-10=20 <= 24 yes -> B [24,30]
        # now A=[0,8], B=[24,30]; an event at 16 is within gap of A (8+10=18>=16)
        # and within gap of B (24-10=14<=16) -> bridges
        s.add_event(16)
        spans = s.spans()
        assert len(spans) == 1
        assert spans[0][0] == 0
        assert spans[0][1] == 30

    def test_the_merged_count_is_the_sum_plus_the_bridge(self):
        s = SessionWindowMerge(gap=10)
        s.add_event(0)
        s.add_event(5)  # session A: two events, span [0,5]
        s.add_event(20)
        s.add_event(25)  # session B: two events, span [20,25]
        assert len(s.spans()) == 2
        # 12 is within a gap of both A (end 5, +10=15) and B (start 20, -10=10)
        s.add_event(12)
        spans = s.spans()
        assert spans == [(0, 25, 5)]  # two plus two plus the bridge


class TestRefusal:
    def test_a_non_positive_gap_is_refused(self):
        with pytest.raises(Invalid):
            SessionWindowMerge(gap=0)


class TestNote:
    def test_the_note_counts_sessions(self):
        s = SessionWindowMerge(gap=10)
        s.add_event(0)
        assert "1 session(s)" in s.note()
