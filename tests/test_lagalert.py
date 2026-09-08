from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.lagalert import LagAlerter


def alerter() -> LagAlerter:
    return LagAlerter(lag_floor=1000, window=5)


class TestNoAlert:
    def test_lag_below_the_floor_is_negligible(self):
        a = alerter()
        a.observe(0, 100)
        a.observe(10, 200)
        assert "below the floor" in a.evaluate()

    def test_high_but_draining_lag_needs_no_human(self):
        a = alerter()
        a.observe(0, 5000)
        a.observe(10, 3000)
        verdict = a.evaluate()
        assert "high but draining" in verdict
        assert "a system recovering" in verdict


class TestAlert:
    def test_growing_lag_above_the_floor_alerts(self):
        a = alerter()
        a.observe(0, 2000)
        a.observe(10, 4000)
        verdict = a.evaluate()
        assert "ALERT" in verdict
        assert "turns latency into loss" in verdict


class TestRefusals:
    def test_a_bad_window_is_refused(self):
        with pytest.raises(Invalid):
            LagAlerter(lag_floor=100, window=1)

    def test_negative_lag_is_refused(self):
        with pytest.raises(Invalid):
            alerter().observe(0, -5)

    def test_time_must_advance(self):
        a = alerter()
        a.observe(10, 100)
        with pytest.raises(Invalid):
            a.observe(5, 200)


class TestWindow:
    def test_the_window_bounds_the_samples(self):
        a = alerter()
        for tick in range(10):
            a.observe(tick, 1000 + tick)
        assert len(a.samples) == 5
