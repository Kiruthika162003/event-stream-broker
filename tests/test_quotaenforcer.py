from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.quotaenforcer import QuotaEnforcer


class TestThrottle:
    def test_a_client_within_quota_is_not_delayed(self):
        q = QuotaEnforcer(quota_bytes_per_sec=1000, window_seconds=1.0)
        assert q.record(now=0.0, byte_count=500) == 0.0

    def test_a_client_exactly_at_quota_waits_zero(self):
        q = QuotaEnforcer(quota_bytes_per_sec=1000, window_seconds=1.0)
        assert q.record(now=0.0, byte_count=1000) == 0.0

    def test_double_the_quota_over_the_window_waits_one_window(self):
        q = QuotaEnforcer(quota_bytes_per_sec=1000, window_seconds=1.0)
        # 2000 bytes where 1000 was allowed: overage 1000 / 1000 per sec = 1s
        assert q.record(now=0.0, byte_count=2000) == pytest.approx(1.0)

    def test_the_delay_scales_with_the_overage(self):
        q = QuotaEnforcer(quota_bytes_per_sec=1000, window_seconds=1.0)
        # 1500 bytes: overage 500 / 1000 = 0.5s
        assert q.record(now=0.0, byte_count=1500) == pytest.approx(0.5)


class TestWindow:
    def test_a_new_window_carries_nothing_across(self):
        q = QuotaEnforcer(quota_bytes_per_sec=1000, window_seconds=1.0)
        q.record(now=0.0, byte_count=2000)  # over quota this window
        # a full window later, the counter resets
        delay = q.record(now=1.0, byte_count=500)
        assert delay == 0.0

    def test_bytes_within_a_window_accumulate(self):
        q = QuotaEnforcer(quota_bytes_per_sec=1000, window_seconds=1.0)
        q.record(now=0.0, byte_count=600)
        delay = q.record(now=0.5, byte_count=600)  # 1200 total, over
        assert delay == pytest.approx(0.2)


class TestConfig:
    def test_a_zero_quota_is_refused(self):
        with pytest.raises(Invalid):
            QuotaEnforcer(quota_bytes_per_sec=0)

    def test_a_zero_window_is_refused(self):
        with pytest.raises(Invalid):
            QuotaEnforcer(quota_bytes_per_sec=1000, window_seconds=0)


class TestNote:
    def test_the_note_states_percent_of_quota(self):
        q = QuotaEnforcer(quota_bytes_per_sec=1000, window_seconds=1.0)
        q.record(now=0.0, byte_count=500)
        assert "50% of quota" in q.note()
