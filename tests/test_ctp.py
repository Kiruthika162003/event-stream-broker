from __future__ import annotations

import pytest

from relay.ctp import ProcessingTransaction, bare_commit_check
from relay.errors import Invalid


def txn() -> ProcessingTransaction:
    return ProcessingTransaction(exactly_once=True)


class TestAtomicCommit:
    def test_output_and_offset_commit_together(self):
        t = txn()
        t.begin()
        t.produce("output", 0)
        t.commit_offset("g", 0, 100)
        verdict = t.commit()
        assert "atomically" in verdict
        assert "replays only unshipped input" in verdict

    def test_exactly_once_requires_the_offset_inside(self):
        t = txn()
        t.begin()
        t.produce("output", 0)
        with pytest.raises(Invalid) as caught:
            t.commit()
        assert "duplicates on a crash" in str(caught.value)

    def test_abort_rolls_back_both_halves(self):
        t = txn()
        t.begin()
        t.produce("output", 0)
        t.commit_offset("g", 0, 100)
        verdict = t.abort()
        assert "neither half survives" in verdict


class TestGuards:
    def test_produce_outside_a_transaction_is_refused(self):
        with pytest.raises(Invalid):
            txn().produce("output", 0)

    def test_a_double_begin_is_refused(self):
        t = txn()
        t.begin()
        with pytest.raises(Invalid):
            t.begin()

    def test_at_least_once_allows_output_without_offset(self):
        t = ProcessingTransaction(exactly_once=False)
        t.begin()
        t.produce("output", 0)
        assert "atomically" in t.commit()


class TestBareCommit:
    def test_a_bare_commit_in_exactly_once_is_the_bug(self):
        with pytest.raises(Invalid) as caught:
            bare_commit_check(exactly_once=True)
        assert "silently reintroduced by a convenience method" in (
            str(caught.value)
        )

    def test_at_least_once_may_bare_commit(self):
        bare_commit_check(exactly_once=False)
