from __future__ import annotations

import statistics

import pytest

from relay.errors import Invalid
from relay.runningmedian import RunningMedian


class TestMedian:
    def test_an_odd_count_has_a_middle_value(self):
        m = RunningMedian()
        for v in (5, 1, 3):
            m.add(v)
        assert m.median() == 3

    def test_an_even_count_averages_the_two_middle(self):
        m = RunningMedian()
        for v in (1, 2, 3, 4):
            m.add(v)
        assert m.median() == 2.5

    def test_it_matches_a_brute_force_median(self):
        values = [7, 2, 9, 1, 5, 3, 8, 4, 6]
        m = RunningMedian()
        seen = []
        for v in values:
            m.add(v)
            seen.append(v)
            assert m.median() == statistics.median(seen)

    def test_an_outlier_barely_moves_the_median(self):
        m = RunningMedian()
        for v in (10, 11, 12, 13, 14):
            m.add(v)
        before = m.median()
        m.add(100000)  # an extreme outlier
        # the median moves at most to the next value, not toward the outlier
        assert m.median() - before <= 1

    def test_the_median_before_any_value_is_refused(self):
        with pytest.raises(Invalid):
            RunningMedian().median()


class TestBalance:
    def test_the_heaps_stay_balanced(self):
        m = RunningMedian()
        for v in range(10):
            m.add(v)
        assert "lower 5, upper 5" in m.balance()
