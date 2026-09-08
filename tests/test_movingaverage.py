from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.movingaverage import MovingAverage


class TestAverage:
    def test_it_averages_the_window(self):
        m = MovingAverage(window=3)
        m.add(10)
        m.add(20)
        assert m.add(30) == 20

    def test_old_samples_drop_out_of_the_window(self):
        m = MovingAverage(window=3)
        for v in (10, 20, 30, 60):
            m.add(v)
        # window is [20, 30, 60] -> mean 36.67
        assert round(m.average(), 2) == 36.67

    def test_a_partial_window_averages_what_is_there(self):
        m = MovingAverage(window=5)
        m.add(10)
        m.add(20)
        assert m.average() == 15

    def test_the_average_of_an_empty_window_is_refused(self):
        with pytest.raises(Invalid):
            MovingAverage(window=3).average()


class TestFull:
    def test_a_young_window_is_flagged(self):
        m = MovingAverage(window=5)
        m.add(1)
        assert not m.is_full()
        assert "overstating how settled" in m.fill_note()

    def test_a_full_window_notes_the_lag(self):
        m = MovingAverage(window=2)
        m.add(1)
        m.add(2)
        assert m.is_full()
        assert "lags the real value" in m.fill_note()


class TestConfig:
    def test_a_zero_window_is_refused(self):
        with pytest.raises(Invalid):
            MovingAverage(window=0)
