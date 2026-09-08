from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.timestampskew import SkewGuard


class TestCheck:
    def test_a_record_within_the_skew_is_accepted(self):
        g = SkewGuard(max_skew=1000)
        assert "within the skew" in g.check(record_ts=1500, broker_now=1000)

    def test_a_record_too_far_ahead_is_rejected(self):
        g = SkewGuard(max_skew=1000)
        with pytest.raises(Invalid) as caught:
            g.check(record_ts=5000, broker_now=1000)
        assert "broken clock" in str(caught.value)

    def test_an_old_record_is_accepted(self):
        g = SkewGuard(max_skew=1000)
        assert "within the skew" in g.check(record_ts=500, broker_now=1000)


class TestFuturePoison:
    def test_a_far_future_record_is_poison(self):
        g = SkewGuard(max_skew=1000)
        assert g.is_future_poison(record_ts=9000, broker_now=1000)

    def test_a_near_record_is_not(self):
        g = SkewGuard(max_skew=1000)
        assert not g.is_future_poison(record_ts=1500, broker_now=1000)


class TestConfig:
    def test_a_negative_skew_is_refused(self):
        with pytest.raises(Invalid):
            SkewGuard(max_skew=-1)


class TestDrift:
    def test_a_past_record_is_normal(self):
        g = SkewGuard(max_skew=1000)
        assert "normal past event" in g.drift_note(record_ts=500, broker_now=1000)

    def test_drift_toward_the_bound_is_flagged(self):
        g = SkewGuard(max_skew=1000)
        note = g.drift_note(record_ts=1900, broker_now=1000)
        assert "100 before the skew bound" in note
