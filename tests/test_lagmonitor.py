from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.lagmonitor import LagMonitor


def draining() -> LagMonitor:
    monitor = LagMonitor()
    for tick, lag in [(0, 10000), (10, 8000), (20, 6000)]:
        monitor.observe(tick, lag)
    return monitor


def growing() -> LagMonitor:
    monitor = LagMonitor()
    for tick, lag in [(0, 1000), (10, 3000), (20, 5000)]:
        monitor.observe(tick, lag)
    return monitor


class TestTheTrend:
    def test_a_draining_consumer_gets_an_eta_not_a_page(self):
        verdict = draining().verdict()
        assert "draining, empty in about" in verdict
        assert "a shrug, not a page" in verdict
        assert not draining().should_page()

    def test_a_growing_consumer_is_a_page(self):
        verdict = growing().verdict()
        assert "losing the race and never empties" in verdict
        assert growing().should_page()

    def test_flat_lag_holds_steady(self):
        monitor = LagMonitor()
        monitor.observe(0, 500)
        monitor.observe(10, 500)
        assert "flat; holding steady" in monitor.verdict()

    def test_zero_lag_is_caught_up(self):
        monitor = LagMonitor()
        monitor.observe(0, 100)
        monitor.observe(10, 0)
        assert "caught up" in monitor.verdict()


class TestNoSingleSampleAlarms:
    def test_one_sample_is_not_a_trend(self):
        monitor = LagMonitor()
        monitor.observe(0, 99999)
        with pytest.raises(Invalid) as caught:
            monitor.verdict()
        assert "not a trend" in str(caught.value)
        assert not monitor.should_page()


class TestRefusals:
    def test_negative_lag_is_refused(self):
        with pytest.raises(Invalid):
            LagMonitor().observe(0, -1)

    def test_time_must_advance(self):
        monitor = LagMonitor()
        monitor.observe(10, 5)
        with pytest.raises(Invalid):
            monitor.observe(5, 5)
