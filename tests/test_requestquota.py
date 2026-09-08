from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.requestquota import RequestQuota


class TestThrottle:
    def test_usage_within_the_allowance_is_not_throttled(self):
        q = RequestQuota(allowance_pct=50)
        assert q.throttle_ticks(used_pct=40, window_ticks=100) == 0

    def test_usage_over_the_allowance_delays_proportionally(self):
        q = RequestQuota(allowance_pct=50)
        # used 75, allowance 50, overage 25 -> 100 * 25/50 = 50 ticks
        assert q.throttle_ticks(used_pct=75, window_ticks=100) == 50

    def test_double_the_allowance_delays_a_full_window(self):
        q = RequestQuota(allowance_pct=50)
        assert q.throttle_ticks(used_pct=100, window_ticks=100) == 100


class TestConfig:
    def test_a_non_positive_allowance_is_refused(self):
        with pytest.raises(Invalid):
            RequestQuota(allowance_pct=0)

    def test_an_allowance_over_capacity_is_refused(self):
        with pytest.raises(Invalid) as caught:
            RequestQuota(allowance_pct=150, thread_capacity_pct=100)
        assert "more thread time than exists" in str(caught.value)


class TestEvaluate:
    def test_a_within_quota_client_is_reported_clear(self):
        q = RequestQuota(allowance_pct=50)
        assert "no throttle" in q.evaluate(used_pct=30, window_ticks=100)

    def test_a_flood_is_named_as_cpu_not_bytes(self):
        q = RequestQuota(allowance_pct=50)
        note = q.evaluate(used_pct=90, window_ticks=100)
        assert "invisible on a bytes dashboard" in note
