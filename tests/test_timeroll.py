from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.timeroll import TimeRollPolicy


def policy() -> TimeRollPolicy:
    return TimeRollPolicy(max_bytes=1000, max_open_ticks=100)


class TestRolling:
    def test_a_full_segment_rolls_by_size(self):
        p = policy()
        verdict = p.should_roll(
            segment_bytes=1200, opened_at=0, now=10, has_records=True
        )
        assert "roll by size" in verdict
        assert p.size_rolls == 1

    def test_an_old_slow_segment_rolls_by_age(self):
        p = policy()
        verdict = p.should_roll(
            segment_bytes=50, opened_at=0, now=200, has_records=True
        )
        assert "roll by age" in verdict
        assert "rescued from retention starvation" in verdict
        assert p.time_rolls == 1

    def test_a_young_small_segment_does_not_roll(self):
        p = policy()
        verdict = p.should_roll(
            segment_bytes=50, opened_at=0, now=10, has_records=True
        )
        assert "no roll" in verdict

    def test_an_empty_segment_never_rolls(self):
        p = policy()
        verdict = p.should_roll(
            segment_bytes=0, opened_at=0, now=999, has_records=False
        )
        assert "empty segment does not roll" in verdict

    def test_size_takes_precedence_when_both_fire(self):
        p = policy()
        verdict = p.should_roll(
            segment_bytes=2000, opened_at=0, now=200, has_records=True
        )
        assert "roll by size" in verdict


class TestRefusals:
    def test_bad_limits_are_refused(self):
        with pytest.raises(Invalid):
            TimeRollPolicy(max_bytes=0, max_open_ticks=100)


class TestTheReport:
    def test_the_report_flags_rising_time_rolls(self):
        p = policy()
        p.should_roll(50, 0, 200, True)
        p.should_roll(2000, 0, 10, True)
        report = p.report()
        assert "1 size roll(s), 1 time roll(s)" in report
        assert "a workload change worth noticing" in report
