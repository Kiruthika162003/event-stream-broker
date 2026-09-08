from __future__ import annotations

import pytest

from relay.errorbudget import ErrorBudget
from relay.errors import Invalid


class TestBudget:
    def test_the_budget_is_the_gap_from_perfect(self):
        # 99% over 1000s -> 10s budget
        b = ErrorBudget(target_pct=99, window_seconds=1000)
        assert b.budget_seconds() == 10

    def test_remaining_subtracts_consumption(self):
        b = ErrorBudget(target_pct=99, window_seconds=1000, consumed_seconds=4)
        assert b.remaining() == 6


class TestRefusals:
    def test_a_hundred_percent_target_is_refused(self):
        with pytest.raises(Invalid):
            ErrorBudget(target_pct=100, window_seconds=1000)

    def test_a_zero_target_is_refused(self):
        with pytest.raises(Invalid):
            ErrorBudget(target_pct=0, window_seconds=1000)


class TestFreeze:
    def test_an_overspent_budget_is_frozen(self):
        b = ErrorBudget(target_pct=99, window_seconds=1000, consumed_seconds=10)
        assert b.is_frozen()
        assert "frozen" in b.report()

    def test_budget_with_room_can_ship(self):
        b = ErrorBudget(target_pct=99, window_seconds=1000, consumed_seconds=2)
        assert not b.is_frozen()
        assert "can ship" in b.report()


class TestBurnRate:
    def test_a_sustainable_burn_is_one(self):
        b = ErrorBudget(target_pct=99, window_seconds=1000)
        # sustainable = 10/1000 = 0.01/s; spending 1s over 100s = 0.01/s
        assert b.burn_rate(over_seconds=100, spent=1) == 1.0

    def test_a_fast_burn_exceeds_one(self):
        b = ErrorBudget(target_pct=99, window_seconds=1000)
        assert b.burn_rate(over_seconds=100, spent=5) == 5.0

    def test_a_non_positive_burn_window_is_refused(self):
        b = ErrorBudget(target_pct=99, window_seconds=1000)
        with pytest.raises(Invalid):
            b.burn_rate(over_seconds=0, spent=1)
