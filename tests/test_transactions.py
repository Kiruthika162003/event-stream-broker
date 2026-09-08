from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.transactions import (
    ABORTED,
    COMMITTED,
    OPEN,
    Transaction,
    visible_to_read_committed,
)


def txn() -> Transaction:
    built = Transaction(txn_id="t-1", opened_at=0, timeout=100)
    built.append(0, 10)
    built.append(1, 20)
    built.append(0, 11)
    return built


class TestAppending:
    def test_records_join_an_open_transaction(self):
        built = txn()
        assert built.partitions_touched == {0, 1}
        assert len(built.records) == 3

    def test_a_closed_transaction_refuses_records(self):
        built = txn()
        built.commit()
        with pytest.raises(Invalid):
            built.append(2, 30)


class TestTheStateMachine:
    def test_commit_walks_through_committing(self):
        built = txn()
        verdict = built.commit()
        assert built.state == COMMITTED
        assert "markers make the records visible together" in (
            verdict
        )

    def test_abort_keeps_records_durable_but_invisible(self):
        built = txn()
        verdict = built.abort()
        assert built.state == ABORTED
        assert "durable but invisible" in verdict

    def test_commit_after_abort_is_refused(self):
        built = txn()
        built.abort()
        with pytest.raises(Invalid) as caught:
            built.commit()
        assert "the edge does not exist" in str(caught.value)

    def test_a_fresh_transaction_is_open(self):
        assert Transaction("t", 0, 10).state == OPEN


class TestTimeout:
    def test_a_zombie_is_force_aborted(self):
        built = txn()
        note = built.force_abort_if_expired(now=200)
        assert note is not None
        assert "will not block read-committed consumers" in note
        assert built.state == ABORTED

    def test_a_young_transaction_is_left_open(self):
        assert txn().force_abort_if_expired(now=50) is None


class TestVisibility:
    def test_only_committed_records_are_visible(self):
        records = [
            (0, 10, COMMITTED),
            (0, 11, "open"),
            (1, 20, ABORTED),
            (1, 21, COMMITTED),
        ]
        assert visible_to_read_committed(records) == [
            (0, 10),
            (1, 21),
        ]
