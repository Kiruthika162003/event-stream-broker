from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.retrybudget import RetryBudget


class TestRetry:
    def test_retries_are_allowed_within_the_budget(self):
        b = RetryBudget(ratio=0.5)
        for _ in range(10):
            b.record_request()
        # ratio 0.5 of 10 requests -> up to 5 retries
        for _ in range(5):
            b.retry()
        assert b.retries == 5

    def test_a_retry_over_the_budget_is_refused(self):
        b = RetryBudget(ratio=0.1)
        for _ in range(10):
            b.record_request()
        b.retry()  # 1 retry, 10 requests -> at the cap
        with pytest.raises(Invalid) as caught:
            b.retry()
        assert "budget exhausted" in str(caught.value)

    def test_more_traffic_grows_the_budget(self):
        b = RetryBudget(ratio=0.1)
        for _ in range(100):
            b.record_request()
        for _ in range(10):
            b.retry()
        assert b.retries == 10


class TestConfig:
    def test_a_ratio_of_one_is_refused(self):
        with pytest.raises(Invalid):
            RetryBudget(ratio=1.0)

    def test_a_zero_ratio_is_refused(self):
        with pytest.raises(Invalid):
            RetryBudget(ratio=0.0)


class TestReport:
    def test_the_ratio_is_reported(self):
        b = RetryBudget(ratio=0.5)
        for _ in range(10):
            b.record_request()
        b.retry()
        assert "retry ratio 0.10 against cap 0.5" in b.current_ratio()
