from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.intervalscheduler import schedule_report, select


class TestSelect:
    def test_it_picks_the_max_non_overlapping_set(self):
        # greedy by earliest finish picks (1,3),(4,7),(8,10); no 4 fit
        intervals = [(1, 3), (2, 5), (4, 7), (1, 8), (5, 9), (8, 10), (9, 11)]
        chosen = select(intervals)
        assert chosen == [(1, 3), (4, 7), (8, 10)]

    def test_non_overlapping_intervals_all_fit(self):
        assert len(select([(0, 1), (1, 2), (2, 3)])) == 3

    def test_all_overlapping_fits_one(self):
        assert len(select([(0, 10), (1, 9), (2, 8)])) == 1

    def test_earliest_finish_is_chosen_first(self):
        chosen = select([(0, 5), (0, 2), (0, 3)])
        assert chosen == [(0, 2)]

    def test_a_backwards_interval_is_refused(self):
        with pytest.raises(Invalid) as caught:
            select([(5, 3)])
        assert "before it starts" in str(caught.value)


class TestReport:
    def test_it_reports_the_fit_ratio(self):
        note = schedule_report([(0, 10), (1, 9), (0, 1)])
        assert "interval(s) fit without overlap" in note

    def test_no_intervals_schedules_nothing(self):
        assert "nothing to schedule" in schedule_report([])
