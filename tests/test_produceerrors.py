from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.produceerrors import classify, should_retry


class TestRetriable:
    def test_not_leader_is_retriable(self):
        assert "retriable" in classify("not-leader", idempotent=False)
        assert should_retry("not-leader", idempotent=False)

    def test_timeout_is_retriable(self):
        assert should_retry("request-timeout", idempotent=False)


class TestFatal:
    def test_message_too_large_is_fatal(self):
        verdict = classify("message-too-large", idempotent=True)
        assert "fatal" in verdict
        assert "do not loop" in verdict
        assert not should_retry("message-too-large", idempotent=True)

    def test_authorization_failed_is_fatal(self):
        assert not should_retry(
            "authorization-failed", idempotent=True
        )


class TestAmbiguous:
    def test_ack_lost_is_retriable_with_idempotence(self):
        verdict = classify("ack-lost", idempotent=True)
        assert "retriable" in verdict
        assert "idempotence dedups a retry" in verdict

    def test_ack_lost_is_fatal_without_idempotence(self):
        verdict = classify("ack-lost", idempotent=False)
        assert "fatal without idempotence" in verdict
        assert "could duplicate" in verdict
        assert not should_retry("ack-lost", idempotent=False)


class TestRefusals:
    def test_an_unknown_error_is_refused(self):
        with pytest.raises(Invalid):
            classify("cosmic-ray", idempotent=True)
