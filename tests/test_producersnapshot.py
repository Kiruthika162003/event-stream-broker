from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.producersnapshot import (
    ProducerEntry,
    ProducerSnapshot,
    SnapshotLoader,
)


class TestLoad:
    def test_loading_populates_the_dedup_state(self):
        loader = SnapshotLoader(recovered_log_end=1000)
        snap = ProducerSnapshot(
            offset=800,
            entries=[ProducerEntry(1, 40), ProducerEntry(2, 90)],
        )
        assert "loaded 2 producer(s) at 800" in loader.load(snap)
        assert loader.state[1].last_seq == 40

    def test_a_snapshot_past_the_recovered_end_is_refused(self):
        loader = SnapshotLoader(recovered_log_end=1000)
        snap = ProducerSnapshot(offset=1500, entries=[])
        with pytest.raises(Invalid) as caught:
            loader.load(snap)
        assert "no longer exist" in str(caught.value)

    def test_an_older_snapshot_cannot_overwrite_a_newer_one(self):
        loader = SnapshotLoader(recovered_log_end=1000)
        loader.load(ProducerSnapshot(offset=800, entries=[]))
        with pytest.raises(Invalid) as caught:
            loader.load(ProducerSnapshot(offset=500, entries=[]))
        assert "newest holds the truth" in str(caught.value)


class TestTail:
    def test_the_tail_is_what_follows_the_snapshot(self):
        loader = SnapshotLoader(recovered_log_end=1000)
        loader.load(ProducerSnapshot(offset=900, entries=[]))
        assert loader.tail_to_replay() == 100

    def test_without_a_snapshot_the_whole_log_replays(self):
        loader = SnapshotLoader(recovered_log_end=1000)
        assert loader.tail_to_replay() == 1000


class TestOpenTransactions:
    def test_producers_mid_transaction_are_surfaced(self):
        loader = SnapshotLoader(recovered_log_end=1000)
        loader.load(
            ProducerSnapshot(
                offset=800,
                entries=[
                    ProducerEntry(1, 40, open_txn_first_offset=780),
                    ProducerEntry(2, 90),
                ],
            )
        )
        assert loader.open_transactions() == [1]


class TestSavings:
    def test_savings_names_the_tail(self):
        loader = SnapshotLoader(recovered_log_end=1000)
        loader.load(ProducerSnapshot(offset=950, entries=[]))
        assert "tail of 50 record(s)" in loader.savings()
