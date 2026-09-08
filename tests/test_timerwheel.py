from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.timerwheel import TimerWheel


class TestSchedule:
    def test_a_timeout_fires_when_its_tick_is_reached(self):
        w = TimerWheel(slots=8)
        w.schedule("a", expiry=3)
        w.schedule("b", expiry=5)
        assert w.advance(to=4) == ["a"]
        assert w.advance(to=5) == ["b"]

    def test_a_past_expiry_is_refused(self):
        w = TimerWheel(slots=8, now=5)
        with pytest.raises(Invalid) as caught:
            w.schedule("a", expiry=3)
        assert "fire immediately" in str(caught.value)

    def test_an_expiry_beyond_the_span_is_refused(self):
        w = TimerWheel(slots=8)
        with pytest.raises(Invalid) as caught:
            w.schedule("a", expiry=100)
        assert "beyond the wheel's span" in str(caught.value)

    def test_a_full_span_expiry_still_fires(self):
        w = TimerWheel(slots=8)
        w.schedule("edge", expiry=8)
        assert w.advance(to=8) == ["edge"]


class TestAdvance:
    def test_advancing_backwards_is_refused(self):
        w = TimerWheel(slots=8, now=5)
        with pytest.raises(Invalid) as caught:
            w.advance(to=3)
        assert "time moves one way" in str(caught.value)

    def test_multiple_timeouts_in_range_all_fire(self):
        w = TimerWheel(slots=16)
        w.schedule("a", 2)
        w.schedule("b", 3)
        w.schedule("c", 10)
        assert set(w.advance(to=5)) == {"a", "b"}
        assert w.advance(to=10) == ["c"]


class TestPending:
    def test_pending_counts_across_the_wheel(self):
        w = TimerWheel(slots=8)
        w.schedule("a", 2)
        w.schedule("b", 3)
        assert "2 timeout(s) pending" in w.pending()
