from __future__ import annotations

import pytest

from relay.deliverytimeout import DeliveryAttempt
from relay.errors import Invalid


def attempt() -> DeliveryAttempt:
    return DeliveryAttempt(
        delivery_timeout=100, base_backoff=10, started_at=0
    )


class TestBackoff:
    def test_backoff_doubles_within_the_window(self):
        d = attempt()
        assert "retrying after 10 tick(s)" in d.try_send(0, False)
        assert "retrying after 20 tick(s)" in d.try_send(10, False)
        assert "retrying after 40 tick(s)" in d.try_send(30, False)

    def test_a_bad_configuration_is_refused(self):
        with pytest.raises(Invalid):
            DeliveryAttempt(
                delivery_timeout=0, base_backoff=1, started_at=0
            )


class TestFinalAnswer:
    def test_success_is_definitive_with_the_attempt(self):
        d = attempt()
        verdict = d.try_send(5, succeeded=True)
        assert "delivered on attempt 1" in verdict
        assert d.is_final()

    def test_the_window_ends_the_attempt_not_a_count(self):
        d = attempt()
        d.try_send(0, False)
        d.try_send(10, False)
        d.try_send(30, False)
        verdict = d.try_send(70, False)
        assert "would expire before the next retry" in verdict
        assert "never silent limbo" in verdict
        assert d.is_final()

    def test_a_resolved_delivery_refuses_further_sends(self):
        d = attempt()
        d.try_send(5, succeeded=True)
        with pytest.raises(Invalid):
            d.try_send(6, succeeded=False)
