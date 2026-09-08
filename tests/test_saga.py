from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.saga import COMMITTED, Saga


def _saga():
    return Saga(steps=["reserve", "charge", "ship"])


class TestForward:
    def test_completing_all_steps_commits(self):
        s = _saga()
        s.complete_step("reserve")
        s.complete_step("charge")
        assert "committed" in s.complete_step("ship")
        assert s.state == COMMITTED

    def test_an_unknown_step_is_refused(self):
        s = _saga()
        with pytest.raises(Invalid):
            s.complete_step("fly")


class TestCompensation:
    def test_failure_compensates_completed_steps_in_reverse(self):
        s = _saga()
        s.complete_step("reserve")
        s.complete_step("charge")
        order = s.fail()
        assert order == ["charge", "reserve"]

    def test_no_forward_progress_after_a_failure(self):
        s = _saga()
        s.complete_step("reserve")
        s.fail()
        with pytest.raises(Invalid) as caught:
            s.complete_step("charge")
        assert "unwinding" in str(caught.value)

    def test_compensating_an_incomplete_step_is_refused(self):
        s = _saga()
        s.complete_step("reserve")
        with pytest.raises(Invalid) as caught:
            s.compensate_step("charge")
        assert "did not complete" in str(caught.value)


class TestReport:
    def test_a_compensated_saga_is_named(self):
        s = _saga()
        s.complete_step("reserve")
        s.fail()
        assert "as if the operation never happened" in s.report()

    def test_no_steps_is_refused(self):
        with pytest.raises(Invalid):
            Saga(steps=[])
