from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.flushpolicy import (
    EVERY_RECORD,
    LAZY,
    DurabilityConfig,
    durability_source,
    throughput_note,
)


class TestDurabilitySource:
    def test_replication_provides_durability_with_lazy_flush(self):
        config = DurabilityConfig(LAZY, replication_factor=3)
        source = durability_source(config)
        assert "durability from replication" in source
        assert "makes the broker fast" in source

    def test_fsync_alone_is_durable_on_one_machine(self):
        config = DurabilityConfig(EVERY_RECORD, replication_factor=1)
        assert "durability from fsync alone" in durability_source(
            config
        )

    def test_both_is_belt_and_suspenders(self):
        config = DurabilityConfig(EVERY_RECORD, replication_factor=3)
        assert "belt and suspenders" in durability_source(config)

    def test_neither_mechanism_is_refused(self):
        config = DurabilityConfig(LAZY, replication_factor=1)
        with pytest.raises(Invalid) as caught:
            durability_source(config)
        assert "loses acknowledged data" in str(caught.value)


class TestThroughput:
    def test_every_record_caps_at_the_sync_rate(self):
        config = DurabilityConfig(EVERY_RECORD, replication_factor=3)
        assert "capped at the disk sync rate" in throughput_note(
            config
        )

    def test_lazy_flush_is_unbound_by_fsync(self):
        config = DurabilityConfig(LAZY, replication_factor=3)
        assert "unbound by fsync" in throughput_note(config)


class TestRefusals:
    def test_an_unknown_policy_is_refused(self):
        with pytest.raises(Invalid):
            DurabilityConfig("sometimes", replication_factor=3)
