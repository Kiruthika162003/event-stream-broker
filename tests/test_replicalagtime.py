from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.replicalagtime import IsrByTime


class TestInSync:
    def test_a_recently_caught_up_follower_is_in_sync(self):
        isr = IsrByTime(lag_window=100)
        isr.caught_up("f1", now=1000)
        assert isr.in_sync("f1", now=1050)

    def test_a_follower_past_the_window_is_out(self):
        isr = IsrByTime(lag_window=100)
        isr.caught_up("f1", now=1000)
        assert not isr.in_sync("f1", now=1200)

    def test_a_never_caught_up_follower_is_out(self):
        isr = IsrByTime(lag_window=100)
        assert not isr.in_sync("f1", now=1000)

    def test_offset_distance_does_not_matter_only_recency(self):
        # caught up recently; still in-sync regardless of how far a
        # burst pushed the offsets apart
        isr = IsrByTime(lag_window=100)
        isr.caught_up("f1", now=5000)
        assert isr.in_sync("f1", now=5099)


class TestEvict:
    def test_it_evicts_only_stale_followers(self):
        isr = IsrByTime(lag_window=100)
        isr.caught_up("fresh", now=1000)
        isr.caught_up("stale", now=500)
        assert isr.evict(now=1050) == ["stale"]


class TestRefusals:
    def test_a_backwards_clock_is_refused(self):
        isr = IsrByTime(lag_window=100)
        isr.caught_up("f1", now=1000)
        with pytest.raises(Invalid):
            isr.caught_up("f1", now=500)

    def test_a_bad_window_is_refused(self):
        with pytest.raises(Invalid):
            IsrByTime(lag_window=0)


class TestReport:
    def test_report_names_time_since_caught_up(self):
        isr = IsrByTime(lag_window=100)
        isr.caught_up("f1", now=1000)
        assert "last caught up 30 ago" in isr.report("f1", now=1030)
