from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.linger import LingerModel


def model() -> LingerModel:
    return LingerModel(records_per_tick=2.0, max_batch=16)


class TestTheCurve:
    def test_batch_grows_with_linger_until_saturation(self):
        m = model()
        assert m.batch_size_at(0) == 1
        assert m.batch_size_at(4) == 9
        assert m.batch_size_at(8) == 16
        assert m.batch_size_at(20) == 16

    def test_the_knee_is_where_the_batch_saturates(self):
        assert model().optimal_linger(max_linger=20) == 8

    def test_marginal_gain_falls_to_zero_past_the_knee(self):
        m = model()
        assert m.marginal_gain(0) == 2
        assert m.marginal_gain(8) == 0

    def test_negative_linger_is_refused(self):
        with pytest.raises(Invalid):
            model().batch_size_at(-1)


class TestExtremes:
    def test_a_low_rate_finds_a_smaller_knee(self):
        slow = LingerModel(records_per_tick=0.5, max_batch=16)
        knee = slow.optimal_linger(max_linger=50)
        assert knee > 8

    def test_a_bad_model_is_refused(self):
        with pytest.raises(Invalid):
            LingerModel(records_per_tick=0, max_batch=16)


class TestTheReport:
    def test_the_report_names_the_knee_and_both_mistakes(self):
        report = model().report(max_linger=20)
        assert "knee at linger 8: batch grows 1 -> 16" in report
        assert "zero linger leaves free batching" in report
        assert "large linger buys latency" in report
