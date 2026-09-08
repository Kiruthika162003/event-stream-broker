from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.producevalidate import ProduceBatch, ProduceValidator


def validator() -> ProduceValidator:
    return ProduceValidator(
        known_topics={"orders"},
        authorized={("team-a", "orders")},
    )


def batch(**overrides) -> ProduceBatch:
    settings = {
        "topic": "orders",
        "codec": "zstd",
        "declared_count": 2,
        "records": (b"a", b"b"),
    }
    settings.update(overrides)
    return ProduceBatch(**settings)


class TestValidation:
    def test_a_clean_batch_is_accepted_whole(self):
        verdict = validator().validate("team-a", batch())
        assert "accepted for orders, whole or not at all" in (
            verdict
        )

    def test_an_unknown_topic_fails_first(self):
        with pytest.raises(Invalid) as caught:
            validator().validate("team-a", batch(topic="ghost"))
        assert "the cheapest check first" in str(caught.value)

    def test_an_unauthorized_producer_is_refused(self):
        with pytest.raises(Invalid):
            validator().validate("intruder", batch())

    def test_an_empty_batch_is_refused(self):
        with pytest.raises(Invalid):
            validator().validate(
                "team-a", batch(declared_count=0, records=())
            )

    def test_an_unknown_codec_is_refused(self):
        with pytest.raises(Invalid) as caught:
            validator().validate("team-a", batch(codec="rar"))
        assert "cannot decompress" in str(caught.value)

    def test_a_count_mismatch_means_truncation(self):
        with pytest.raises(Invalid) as caught:
            validator().validate(
                "team-a", batch(declared_count=5)
            )
        assert "truncated in transit" in str(caught.value)


class TestOrdering:
    def test_topic_check_precedes_auth_check(self):
        with pytest.raises(Invalid) as caught:
            validator().validate(
                "intruder", batch(topic="ghost")
            )
        assert "does not exist" in str(caught.value)
