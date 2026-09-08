from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.recoverypoint import (
    RecoveryState,
    startup_plan,
    tail_to_verify,
)


class TestCleanShutdown:
    def test_a_clean_shutdown_at_the_end_verifies_nothing(self):
        state = RecoveryState(
            recovery_point=1000, log_end=1000, clean_shutdown=True
        )
        assert tail_to_verify(state) == 0
        assert "verifying nothing" in startup_plan(state)

    def test_a_clean_shutdown_with_a_tail_verifies_it(self):
        state = RecoveryState(
            recovery_point=980, log_end=1000, clean_shutdown=True
        )
        assert "20 record(s) past the recovery point" in (
            startup_plan(state)
        )


class TestCrash:
    def test_a_crash_verifies_the_bounded_tail(self):
        state = RecoveryState(
            recovery_point=900, log_end=1000, clean_shutdown=False
        )
        plan = startup_plan(state)
        assert "crash detected" in plan
        assert "verify 100 record(s)" in plan
        assert "not the whole log" in plan


class TestRefusals:
    def test_a_recovery_point_past_the_end_is_refused(self):
        with pytest.raises(Invalid) as caught:
            RecoveryState(
                recovery_point=1100,
                log_end=1000,
                clean_shutdown=True,
            )
        assert "the exact ones a crash endangers" in str(
            caught.value
        )

    def test_the_tail_is_the_restart_cost(self):
        state = RecoveryState(
            recovery_point=500, log_end=1500, clean_shutdown=False
        )
        assert tail_to_verify(state) == 1000
