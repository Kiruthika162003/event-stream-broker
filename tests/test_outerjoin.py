from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.outerjoin import OuterJoin


class TestMatch:
    def test_a_match_cancels_the_pending_emission(self):
        j = OuterJoin(window=100)
        j.arrive("k", time=10)
        assert "cancelled" in j.match("k")
        # after a match, advancing does not emit it unmatched
        assert j.advance(watermark=500) == []

    def test_matching_an_unknown_key_is_refused(self):
        j = OuterJoin(window=100)
        with pytest.raises(Invalid):
            j.match("k")


class TestUnmatched:
    def test_an_unmatched_record_emits_when_its_window_closes(self):
        j = OuterJoin(window=100)
        j.arrive("k", time=10)
        # watermark past 10+100 -> window closed
        assert j.advance(watermark=200) == ["k"]

    def test_an_unmatched_record_before_close_does_not_emit(self):
        j = OuterJoin(window=100)
        j.arrive("k", time=10)
        assert j.advance(watermark=50) == []

    def test_emitting_before_close_is_refused(self):
        j = OuterJoin(window=100)
        j.arrive("k", time=10)
        with pytest.raises(Invalid) as caught:
            j.emit_unmatched("k", watermark=50)
        assert "could still arrive" in str(caught.value)


class TestReport:
    def test_report_counts_pending(self):
        j = OuterJoin(window=100)
        j.arrive("a", time=1)
        j.arrive("b", time=2)
        assert "2 record(s) pending" in j.report()
