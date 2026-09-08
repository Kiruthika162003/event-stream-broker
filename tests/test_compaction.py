from __future__ import annotations

import pytest

from relay.compaction import Compactor, KeyedEntry
from relay.errors import Invalid


def updates() -> list[KeyedEntry]:
    return [
        KeyedEntry(0, b"user-1", b"addr-a"),
        KeyedEntry(1, b"user-2", b"addr-x"),
        KeyedEntry(2, b"user-1", b"addr-b"),
        KeyedEntry(3, b"user-1", b"addr-c"),
        KeyedEntry(4, b"user-2", b"addr-y"),
    ]


class TestCompaction:
    def test_only_the_last_value_per_key_survives(self):
        compactor = Compactor(tombstone_retention_ticks=100)
        kept = compactor.compact(
            updates(),
            now=0,
            tombstone_ticks={},
            min_consumer_offset=0,
        )
        offsets = [entry.offset for entry in kept]
        assert offsets == [3, 4]
        assert compactor.removed_superseded == 3

    def test_kept_records_preserve_their_offsets(self):
        compactor = Compactor(tombstone_retention_ticks=100)
        kept = compactor.compact(
            updates(),
            now=0,
            tombstone_ticks={},
            min_consumer_offset=0,
        )
        assert compactor.preserves_offsets(kept)

    def test_empty_input_is_refused(self):
        with pytest.raises(Invalid):
            Compactor(tombstone_retention_ticks=1).compact(
                [], now=0, tombstone_ticks={},
                min_consumer_offset=0,
            )


class TestTombstones:
    def test_a_fresh_tombstone_is_kept_for_lagging_readers(self):
        entries = [
            KeyedEntry(0, b"user-1", b"addr-a"),
            KeyedEntry(1, b"user-1", None),
        ]
        compactor = Compactor(tombstone_retention_ticks=100)
        kept = compactor.compact(
            entries,
            now=10,
            tombstone_ticks={1: 5},
            min_consumer_offset=0,
        )
        assert any(e.value is None for e in kept)
        assert compactor.tombstones_reaped == 0

    def test_an_observed_aged_tombstone_is_reaped(self):
        entries = [
            KeyedEntry(0, b"user-1", b"addr-a"),
            KeyedEntry(1, b"user-1", None),
        ]
        compactor = Compactor(tombstone_retention_ticks=100)
        kept = compactor.compact(
            entries,
            now=500,
            tombstone_ticks={1: 5},
            min_consumer_offset=99,
        )
        assert kept == []
        assert compactor.tombstones_reaped == 1


class TestTheReport:
    def test_the_report_states_the_compaction_ratio(self):
        compactor = Compactor(tombstone_retention_ticks=100)
        compactor.compact(
            updates(), now=0, tombstone_ticks={},
            min_consumer_offset=0,
        )
        report = compactor.report(original_count=5)
        assert "5 records compact to 2" in report
        assert "3 superseded removed" in report
