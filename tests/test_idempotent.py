from __future__ import annotations

import pytest

from relay.errors import Fenced, Invalid
from relay.idempotent import IdempotencyGate


def gate() -> IdempotencyGate:
    built = IdempotencyGate()
    built.open_session("producer-a", epoch=1)
    return built


class TestSequencing:
    def test_records_advance_by_one(self):
        built = gate()
        assert built.admit("producer-a", 1, 0, 100) == (
            "accepted sequence 0 at offset 100"
        )
        assert "accepted sequence 1" in built.admit(
            "producer-a", 1, 1, 101
        )

    def test_a_retry_is_answered_with_the_original_offset(self):
        built = gate()
        built.admit("producer-a", 1, 0, 100)
        verdict = built.admit("producer-a", 1, 0, 999)
        assert "already landed at offset 100" in verdict
        assert built.duplicates_absorbed == 1

    def test_a_gap_means_a_lost_record(self):
        built = gate()
        built.admit("producer-a", 1, 0, 100)
        with pytest.raises(Invalid) as caught:
            built.admit("producer-a", 1, 2, 101)
        assert "a hole the producer cannot see" in str(
            caught.value
        )

    def test_a_negative_starting_sequence_is_a_producer_bug(self):
        built = gate()
        with pytest.raises(Invalid) as caught:
            built.admit("producer-a", 1, -1, 100)
        assert "this is a producer bug, not a retry" in str(
            caught.value
        )


class TestFencing:
    def test_a_zombie_epoch_is_refused_at_open(self):
        built = gate()
        built.open_session("producer-a", epoch=2)
        with pytest.raises(Fenced) as caught:
            built.open_session("producer-a", epoch=1)
        assert "zombie producer resuming after a partition" in (
            str(caught.value)
        )

    def test_an_old_epoch_write_is_fenced(self):
        built = gate()
        built.open_session("producer-a", epoch=5)
        with pytest.raises(Fenced):
            built.admit("producer-a", 3, 0, 100)

    def test_producing_without_a_session_is_refused(self):
        with pytest.raises(Invalid):
            IdempotencyGate().admit("ghost", 1, 0, 0)


class TestTheLedger:
    def test_the_ledger_counts_absorbed_duplicates(self):
        built = gate()
        built.admit("producer-a", 1, 0, 100)
        built.admit("producer-a", 1, 0, 100)
        built.admit("producer-a", 1, 0, 100)
        assert "2 duplicate(s) absorbed" in built.ledger()
