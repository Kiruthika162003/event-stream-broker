from __future__ import annotations

import pytest

from relay.backoff import BackoffPolicy, spread_of_fleet
from relay.errors import Invalid


def policy() -> BackoffPolicy:
    return BackoffPolicy(base=10, ceiling=1000)


class TestWindow:
    def test_the_window_doubles_per_attempt(self):
        p = policy()
        assert p.window(0) == 10
        assert p.window(1) == 20
        assert p.window(2) == 40

    def test_the_window_caps_at_the_ceiling(self):
        p = policy()
        assert p.window(20) == 1000

    def test_a_negative_attempt_is_refused(self):
        with pytest.raises(Invalid):
            policy().window(-1)


class TestJitter:
    def test_jitter_stays_within_the_window(self):
        p = policy()
        assert p.jittered(3, roll=1.0) == p.window(3)
        assert p.jittered(3, roll=0.0) == 0

    def test_a_bad_roll_is_refused(self):
        with pytest.raises(Invalid):
            policy().jittered(1, roll=1.5)


class TestSpread:
    def test_a_fleet_spreads_across_the_window(self):
        p = policy()
        rolls = [i / 10 for i in range(11)]
        report = spread_of_fleet(p, attempt=4, rolls=rolls)
        assert "window 160" in report
        assert "spread across 160 tick(s)" in report
        assert "the wave that knocks a recovering broker" in report

    def test_no_clients_is_refused(self):
        with pytest.raises(Invalid):
            spread_of_fleet(policy(), attempt=1, rolls=[])

    def test_a_bad_policy_is_refused(self):
        with pytest.raises(Invalid):
            BackoffPolicy(base=0, ceiling=10)
