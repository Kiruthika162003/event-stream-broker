from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.splitvote import SplitVote


def _sv():
    return SplitVote(voters=5, base_timeout=100, jitter_range=50)


class TestSplit:
    def test_a_split_tally_has_no_majority(self):
        sv = _sv()
        assert sv.is_split({"a": 2, "b": 2, "c": 1})

    def test_a_majority_is_not_a_split(self):
        sv = _sv()
        assert not sv.is_split({"a": 3, "b": 2})


class TestStagger:
    def test_timeouts_are_base_plus_jitter(self):
        sv = _sv()
        rolls = {"a": 10, "b": 40}
        timeouts = sv.staggered_timeouts(["a", "b"], roll=lambda n: rolls[n])
        assert timeouts == {"a": 110, "b": 140}

    def test_the_earliest_wakes_first(self):
        sv = _sv()
        rolls = {"a": 30, "b": 5, "c": 45}
        first = sv.first_to_wake(["a", "b", "c"], roll=lambda n: rolls[n])
        assert first == "b"


class TestReport:
    def test_a_win_is_named(self):
        sv = _sv()
        assert "'a' won with 3/5" in sv.report({"a": 3, "b": 2})

    def test_a_split_names_the_tuning(self):
        sv = _sv()
        note = sv.report({"a": 2, "b": 2, "c": 1})
        assert "split vote" in note
        assert "too narrow a timeout range" in note


class TestConfig:
    def test_a_zero_jitter_is_refused(self):
        with pytest.raises(Invalid):
            SplitVote(voters=5, base_timeout=100, jitter_range=0)
