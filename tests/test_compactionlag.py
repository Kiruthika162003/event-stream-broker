from __future__ import annotations

import pytest

from relay.compactionlag import ELIGIBLE, NOT_YET, OVERDUE, CompactionLag
from relay.errors import Invalid


def _lag():
    return CompactionLag(min_lag=100, max_lag=1000)


class TestClassify:
    def test_below_min_is_not_yet(self):
        assert _lag().classify(50) == NOT_YET

    def test_between_is_eligible(self):
        assert _lag().classify(500) == ELIGIBLE

    def test_above_max_is_overdue(self):
        assert _lag().classify(2000) == OVERDUE


class TestRefusals:
    def test_max_below_min_is_refused(self):
        with pytest.raises(Invalid) as caught:
            CompactionLag(min_lag=1000, max_lag=100)
        assert "impossible window" in str(caught.value)

    def test_negative_lag_is_refused(self):
        with pytest.raises(Invalid):
            CompactionLag(min_lag=-1, max_lag=100)


class TestStatus:
    def test_not_yet_reports_the_wait(self):
        assert "not eligible for 50 more" in _lag().status(50)

    def test_overdue_reports_the_deadline_risk(self):
        note = _lag().status(1500)
        assert "overdue by 500" in note
        assert "deletion promise is at risk" in note

    def test_eligible_reports_time_before_overdue(self):
        assert "500 before overdue" in _lag().status(500)
