from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.topicconfig import TopicConfig


def config() -> TopicConfig:
    return TopicConfig(
        replication_factor=3,
        broker_fetch_max_bytes=1000000,
        worst_consumer_lag_ticks=90,
    )


class TestValidOverrides:
    def test_a_sensible_override_is_accepted(self):
        chosen = config()
        assert chosen.set("retention_ticks", 1000) == (
            "retention_ticks set to 1000"
        )
        assert chosen.get("retention_ticks") == 1000

    def test_an_unknown_key_is_refused(self):
        with pytest.raises(Invalid):
            config().set("teleport", 1)


class TestInteractionChecks:
    def test_retention_below_worst_lag_is_data_loss(self):
        with pytest.raises(Invalid) as caught:
            config().set("retention_ticks", 60)
        assert "deletes data before it is read" in str(
            caught.value
        )

    def test_min_in_sync_above_factor_blocks_forever(self):
        with pytest.raises(Invalid) as caught:
            config().set("min_in_sync", 5)
        assert "block forever" in str(caught.value)

    def test_max_message_above_fetch_max_is_poison(self):
        with pytest.raises(Invalid) as caught:
            config().set("max_message_bytes", 2000000)
        assert "poison by configuration" in str(caught.value)


class TestDescribe:
    def test_overrides_and_inheritance_are_distinguished(self):
        chosen = config()
        chosen.set("min_in_sync", 3)
        described = chosen.describe()
        assert "min_in_sync = 3 (override)" in described
        assert "retention_ticks = 604800 (inherited)" in described
