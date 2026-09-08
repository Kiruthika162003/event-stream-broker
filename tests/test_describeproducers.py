from __future__ import annotations

import pytest

from relay.describeproducers import ProducerDirectory, ProducerRecord
from relay.errors import Invalid


class TestOpenTransactions:
    def test_the_lso_blocker_is_the_earliest_open_txn(self):
        d = ProducerDirectory(
            producers=[
                ProducerRecord(1, 0, 40, open_txn_offset=500, txn_open_ticks=10),
                ProducerRecord(2, 0, 90, open_txn_offset=300, txn_open_ticks=50),
                ProducerRecord(3, 0, 20),
            ]
        )
        blocker = d.lso_blocker()
        assert blocker.producer_id == 2

    def test_no_open_transactions_means_no_blocker(self):
        d = ProducerDirectory(producers=[ProducerRecord(1, 0, 40)])
        assert d.lso_blocker() is None


class TestHung:
    def test_a_transaction_past_the_timeout_is_hung(self):
        d = ProducerDirectory(
            producers=[
                ProducerRecord(1, 0, 40, open_txn_offset=500, txn_open_ticks=9999),
            ]
        )
        assert d.hung(txn_timeout=1000) == [1]


class TestReport:
    def test_it_names_the_blocker_and_flags_a_hung_txn(self):
        d = ProducerDirectory(
            producers=[
                ProducerRecord(1, 0, 40, open_txn_offset=500, txn_open_ticks=9999),
            ]
        )
        note = d.report(txn_timeout=1000)
        assert "producer 1 pins the LSO at offset 500" in note
        assert "candidate for forced abort" in note

    def test_no_open_txn_reports_lso_equals_hw(self):
        d = ProducerDirectory(producers=[ProducerRecord(1, 0, 40)])
        assert "LSO equals the high watermark" in d.report(txn_timeout=1000)


class TestLastSequence:
    def test_a_producer_with_no_writes_is_distinguished(self):
        d = ProducerDirectory(producers=[ProducerRecord(9, 0, -1)])
        with pytest.raises(Invalid) as caught:
            d.last_sequence_of(9)
        assert "no writes yet" in str(caught.value)

    def test_an_unknown_producer_is_refused(self):
        d = ProducerDirectory()
        with pytest.raises(Invalid):
            d.last_sequence_of(9)
