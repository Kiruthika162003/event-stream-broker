from __future__ import annotations

import pytest

from relay.circuitbreaker import CLOSED, HALF_OPEN, OPEN, CircuitBreaker
from relay.errors import Invalid


class TestOpening:
    def test_failures_below_threshold_stay_closed(self):
        cb = CircuitBreaker(threshold=3, cooldown=100)
        cb.on_failure(now=0)
        cb.on_failure(now=1)
        assert cb.state == CLOSED

    def test_hitting_the_threshold_opens(self):
        cb = CircuitBreaker(threshold=3, cooldown=100)
        for t in range(3):
            cb.on_failure(now=t)
        assert cb.state == OPEN

    def test_an_open_circuit_fails_fast(self):
        cb = CircuitBreaker(threshold=1, cooldown=100)
        cb.on_failure(now=0)
        with pytest.raises(Invalid) as caught:
            cb.allow(now=50)
        assert "failing fast" in str(caught.value)


class TestRecovery:
    def test_after_cooldown_it_goes_half_open(self):
        cb = CircuitBreaker(threshold=1, cooldown=100)
        cb.on_failure(now=0)
        assert "call allowed in half-open" in cb.allow(now=150)
        assert cb.state == HALF_OPEN

    def test_a_success_in_half_open_closes(self):
        cb = CircuitBreaker(threshold=1, cooldown=100)
        cb.on_failure(now=0)
        cb.allow(now=150)
        cb.on_success(now=151)
        assert cb.state == CLOSED

    def test_a_failure_in_half_open_reopens(self):
        cb = CircuitBreaker(threshold=1, cooldown=100)
        cb.on_failure(now=0)
        cb.allow(now=150)
        note = cb.on_failure(now=151)
        assert "re-opened" in note
        assert cb.state == OPEN


class TestConfig:
    def test_a_bad_threshold_is_refused(self):
        with pytest.raises(Invalid):
            CircuitBreaker(threshold=0, cooldown=100)
