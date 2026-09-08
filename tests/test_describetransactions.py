from __future__ import annotations

import pytest

from relay.describetransactions import (
    COMPLETE,
    DEAD,
    ONGOING,
    PREPARE_COMMIT,
    TransactionDirectory,
    TxnRecord,
)
from relay.errors import Invalid


def _dir():
    return TransactionDirectory(
        transactions=[
            TxnRecord("t1", ONGOING, duration_ticks=50, partitions=3),
            TxnRecord("t2", PREPARE_COMMIT, duration_ticks=9999, partitions=2),
            TxnRecord("t3", COMPLETE, duration_ticks=10, partitions=0),
            TxnRecord("t4", DEAD, duration_ticks=0, partitions=0),
        ]
    )


class TestFilter:
    def test_in_state_filters(self):
        assert [t.txn_id for t in _dir().in_state(ONGOING)] == ["t1"]

    def test_active_excludes_dead(self):
        assert "t4" not in [t.txn_id for t in _dir().active()]


class TestStuck:
    def test_a_long_prepare_is_stuck(self):
        assert _dir().stuck(timeout=1000) == ["t2"]


class TestLongest:
    def test_the_longest_non_terminal_is_named(self):
        assert _dir().longest_non_terminal().txn_id == "t2"

    def test_none_when_all_terminal(self):
        d = TransactionDirectory(
            transactions=[TxnRecord("x", COMPLETE, 5, 0)]
        )
        assert d.longest_non_terminal() is None


class TestReport:
    def test_it_flags_the_stuck_transaction(self):
        note = _dir().report(timeout=1000)
        assert "longest non-terminal 't2'" in note
        assert "force to complete" in note


class TestAssertNotDead:
    def test_a_dead_transaction_is_refused(self):
        with pytest.raises(Invalid) as caught:
            _dir().assert_not_dead("t4")
        assert "points at something gone" in str(caught.value)
