from __future__ import annotations

import pytest

from relay.diskmonitor import DiskMonitor
from relay.errors import Invalid


def monitor() -> DiskMonitor:
    return DiskMonitor(
        total_bytes=1000, stop_write_ratio=0.9, lead_time=100
    )


class TestProjection:
    def test_a_slow_fill_is_informational(self):
        m = monitor()
        m.observe(0, 500)
        m.observe(100, 700)
        verdict = m.ticks_to_stop()
        assert "informational" in verdict
        assert "in about 100 tick(s)" in verdict

    def test_a_fast_fill_within_lead_time_is_actionable(self):
        m = monitor()
        m.observe(0, 850)
        m.observe(50, 880)
        assert "ACTIONABLE" in m.ticks_to_stop()

    def test_retention_holding_steady_is_healthy(self):
        m = monitor()
        m.observe(0, 900)
        m.observe(50, 900)
        assert "retention is working" in m.ticks_to_stop()

    def test_stable_below_the_mark_needs_no_projection(self):
        m = monitor()
        m.observe(0, 500)
        m.observe(50, 500)
        assert "no projection needed" in m.ticks_to_stop()


class TestRefusals:
    def test_used_above_total_is_refused(self):
        with pytest.raises(Invalid):
            monitor().observe(0, 2000)

    def test_time_must_advance(self):
        m = monitor()
        m.observe(10, 100)
        with pytest.raises(Invalid):
            m.observe(5, 200)

    def test_a_bad_ratio_is_refused(self):
        with pytest.raises(Invalid):
            DiskMonitor(total_bytes=1000, stop_write_ratio=0, lead_time=1)

    def test_one_sample_has_no_rate(self):
        m = monitor()
        m.observe(0, 100)
        with pytest.raises(Invalid):
            m.net_fill_rate()
