from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.sizelimits import SizeLimits, validate_record


def limits(**overrides) -> SizeLimits:
    settings = {
        "producer_batch_max": 1000,
        "request_max": 2000,
        "broker_message_max": 500,
        "topic_override": None,
    }
    settings.update(overrides)
    return SizeLimits(**settings)


class TestEarliestGate:
    def test_a_record_over_the_batch_limit_fails_at_the_producer(self):
        with pytest.raises(Invalid) as caught:
            validate_record(limits(), 1500)
        assert "cheapest gate before crossing the network" in str(
            caught.value
        )

    def test_a_record_over_the_broker_limit_fails_there(self):
        with pytest.raises(Invalid) as caught:
            validate_record(limits(), 600)
        assert "ask the operator to raise the topic limit" in str(
            caught.value
        )

    def test_a_fitting_record_passes_every_gate(self):
        verdict = validate_record(limits(), 400)
        assert "fits every gate" in verdict


class TestTopicOverride:
    def test_the_override_allows_larger_messages(self):
        verdict = validate_record(
            limits(topic_override=800), 600
        )
        assert "fits every gate up to the effective limit 800" in (
            verdict
        )

    def test_a_record_over_the_override_still_fails(self):
        with pytest.raises(Invalid) as caught:
            validate_record(limits(topic_override=800), 900)
        assert "topic override" in str(caught.value)

    def test_the_effective_limit_prefers_the_override(self):
        assert limits(topic_override=800).effective_message_max() == 800
        assert limits().effective_message_max() == 500
