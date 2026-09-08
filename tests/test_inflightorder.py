from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.inflightorder import (
    ProducerConfig,
    validate_ordering,
    would_reorder,
)


class TestValidation:
    def test_single_in_flight_preserves_order_by_serialization(self):
        config = ProducerConfig(
            max_in_flight=1, idempotent=False, needs_ordering=True
        )
        assert "order preserved by serialization" in (
            validate_ordering(config)
        )

    def test_idempotence_makes_pipelining_safe(self):
        config = ProducerConfig(
            max_in_flight=5, idempotent=True, needs_ordering=True
        )
        verdict = validate_ordering(config)
        assert "pipelining and order both hold" in verdict
        assert "the reason idempotent producers exist" in verdict

    def test_high_in_flight_without_idempotence_is_refused(self):
        config = ProducerConfig(
            max_in_flight=5, idempotent=False, needs_ordering=True
        )
        with pytest.raises(Invalid) as caught:
            validate_ordering(config)
        assert "a correctness bug hiding behind a performance" in (
            str(caught.value)
        )

    def test_a_producer_not_needing_order_may_pipeline_unsafely(self):
        config = ProducerConfig(
            max_in_flight=5, idempotent=False, needs_ordering=False
        )
        verdict = validate_ordering(config)
        assert "does not need ordering" in verdict


class TestReorderPrediction:
    def test_a_retry_reorders_without_idempotence(self):
        config = ProducerConfig(
            max_in_flight=5, idempotent=False, needs_ordering=False
        )
        assert would_reorder(config, batch_one_failed=True)

    def test_idempotence_prevents_reorder(self):
        config = ProducerConfig(
            max_in_flight=5, idempotent=True, needs_ordering=True
        )
        assert not would_reorder(config, batch_one_failed=True)

    def test_a_bad_config_is_refused(self):
        with pytest.raises(Invalid):
            ProducerConfig(
                max_in_flight=0, idempotent=True, needs_ordering=True
            )
