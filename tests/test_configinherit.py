from __future__ import annotations

import pytest

from relay.configinherit import BROKER, DEFAULT, TOPIC, ConfigResolver
from relay.errors import Missing


def _resolver():
    return ConfigResolver(
        defaults={"retention.ms": "604800000", "cleanup.policy": "delete"},
        broker={"retention.ms": "86400000"},
        topic={"cleanup.policy": "compact"},
    )


class TestResolve:
    def test_a_topic_override_wins(self):
        value, source = _resolver().resolve("cleanup.policy")
        assert value == "compact"
        assert source == TOPIC

    def test_the_broker_value_is_inherited_when_no_topic_override(self):
        value, source = _resolver().resolve("retention.ms")
        assert value == "86400000"
        assert source == BROKER

    def test_the_built_in_default_is_the_last_resort(self):
        r = ConfigResolver(defaults={"segment.bytes": "1073741824"})
        _value, source = r.resolve("segment.bytes")
        assert source == DEFAULT

    def test_an_unknown_key_is_a_typo_not_an_unset_config(self):
        with pytest.raises(Missing) as caught:
            _resolver().resolve("retention.mss")
        assert "typo in the key name" in str(caught.value)


class TestDescribe:
    def test_describe_names_the_source(self):
        assert "(from broker override)" in _resolver().describe("retention.ms")


class TestRedundant:
    def test_a_topic_override_matching_the_broker_is_redundant(self):
        r = ConfigResolver(
            broker={"retention.ms": "1000"},
            topic={"retention.ms": "1000"},
        )
        assert r.redundant_overrides() == ["retention.ms"]

    def test_a_differing_override_is_not_redundant(self):
        assert _resolver().redundant_overrides() == []
