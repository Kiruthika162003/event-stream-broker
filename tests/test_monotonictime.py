from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.monotonictime import MonotonicStamper


class TestMonotonicity:
    def test_a_rising_clock_stamps_directly(self):
        s = MonotonicStamper()
        assert s.stamp(100) == 100
        assert s.stamp(200) == 200
        assert s.clamps == 0

    def test_a_backward_step_is_clamped_not_reversed(self):
        s = MonotonicStamper()
        s.stamp(200)
        assert s.stamp(150) == 200
        assert s.clamps == 1

    def test_equal_timestamps_are_allowed(self):
        s = MonotonicStamper()
        s.stamp(100)
        assert s.stamp(100) == 100
        assert s.clamps == 0

    def test_the_log_never_decreases(self):
        s = MonotonicStamper()
        clock = [100, 200, 150, 250, 240, 300]
        stamps = [s.stamp(c) for c in clock]
        assert stamps == sorted(stamps)

    def test_a_negative_clock_is_refused(self):
        with pytest.raises(Invalid):
            MonotonicStamper().stamp(-1)


class TestClampRate:
    def test_a_high_clamp_rate_flags_the_clock(self):
        s = MonotonicStamper()
        s.stamp(1000)
        for _ in range(9):
            s.stamp(1)
        report = s.clamp_rate()
        assert "9 clamp(s) in 10 stamp(s)" in report
        assert "fix at the source" in report

    def test_no_stamps_cannot_be_rated(self):
        with pytest.raises(Invalid):
            MonotonicStamper().clamp_rate()
