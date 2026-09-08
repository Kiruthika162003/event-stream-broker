from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.segmentroll import RollPlan


def _plan():
    return RollPlan(size_limit=1000, time_limit=500, index_limit=100)


class TestShouldRoll:
    def test_size_triggers_a_roll(self):
        assert _plan().should_roll(size=1000, age=0, index_entries=0)

    def test_time_triggers_a_roll(self):
        assert _plan().should_roll(size=0, age=500, index_entries=0)

    def test_index_triggers_a_roll(self):
        assert _plan().should_roll(size=0, age=0, index_entries=100)

    def test_under_all_limits_does_not_roll(self):
        assert not _plan().should_roll(size=10, age=10, index_entries=10)


class TestTrigger:
    def test_time_roll_says_slow(self):
        assert "the partition is slow" in _plan().trigger(0, 500, 0)

    def test_index_roll_says_small_records(self):
        assert "records are unusually small" in _plan().trigger(0, 0, 100)

    def test_no_roll_reports_under_limit(self):
        assert "under every limit" in _plan().trigger(1, 1, 1)


class TestRemaining:
    def test_it_names_the_soonest_trigger(self):
        # size 900/1000 -> 100 left; time 0/500 -> 500; index 0/100 -> 100
        note = _plan().remaining(size=900, age=0, index_entries=0)
        assert "rolls next on size in 100" in note


class TestConfig:
    def test_a_zero_limit_is_refused(self):
        with pytest.raises(Invalid):
            RollPlan(size_limit=0, time_limit=1, index_limit=1)
