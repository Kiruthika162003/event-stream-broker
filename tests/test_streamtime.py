from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.streamtime import WindowedStream


def stream() -> WindowedStream:
    return WindowedStream(window_size=60, allowed_lateness=10)


class TestOnTime:
    def test_events_land_in_their_event_time_window(self):
        s = stream()
        assert "window [0,60)" in s.add(10, 1)
        assert "window [60,120)" in s.add(65, 1)

    def test_a_bad_configuration_is_refused(self):
        with pytest.raises(Invalid):
            WindowedStream(window_size=0, allowed_lateness=1)


class TestWatermarkAndClosing:
    def test_a_window_closes_past_end_plus_grace(self):
        s = stream()
        s.add(10, 1)
        assert s.advance_watermark(65) == []
        assert s.advance_watermark(75) == [0]

    def test_the_watermark_only_advances(self):
        s = stream()
        s.advance_watermark(50)
        with pytest.raises(Invalid) as caught:
            s.advance_watermark(40)
        assert "breaks every downstream" in str(caught.value)


class TestLateness:
    def test_within_grace_the_window_reopens(self):
        s = stream()
        s.add(10, 1)
        s.advance_watermark(65)
        verdict = s.add(20, 5)
        assert "late but in grace" in verdict
        assert s.result(0) == 6

    def test_past_grace_the_event_is_dropped_and_counted(self):
        s = stream()
        s.add(10, 1)
        s.advance_watermark(75)
        verdict = s.add(30, 5)
        assert "counted as late, not swallowed" in verdict
        assert s.dropped_late == 1

    def test_the_lateness_report_is_actionable(self):
        s = stream()
        s.add(10, 1)
        s.advance_watermark(75)
        s.add(30, 5)
        report = s.lateness_report()
        assert "1 window(s) closed, 1 event(s) dropped" in report
        assert "not a silent wrong aggregate" in report
