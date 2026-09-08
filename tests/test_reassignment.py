from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.reassignment import ReplicaMove


def move() -> ReplicaMove:
    return ReplicaMove(
        partition=0,
        from_broker="b1",
        to_broker="b2",
        total_bytes=1000,
        throttle_bytes_per_tick=100,
    )


class TestThrottling:
    def test_the_eta_is_computed_from_the_rate(self):
        assert move().eta_ticks() == 10

    def test_an_unthrottled_move_is_refused(self):
        with pytest.raises(Invalid) as caught:
            ReplicaMove(0, "b1", "b2", 1000, 0)
        assert "saturates the links" in str(caught.value)

    def test_a_self_move_is_refused(self):
        with pytest.raises(Invalid):
            ReplicaMove(0, "b1", "b1", 1000, 100)


class TestProgress:
    def test_a_partial_move_is_not_yet_in_sync(self):
        chosen = move()
        verdict = chosen.advance(3)
        assert "300 of 1000 bytes" in verdict
        assert not chosen.eligible_for_election()

    def test_a_complete_move_becomes_eligible(self):
        chosen = move()
        verdict = chosen.advance(10)
        assert "now eligible for in-sync and election" in verdict
        assert chosen.eligible_for_election()

    def test_a_half_copied_replica_cannot_be_elected(self):
        chosen = move()
        chosen.advance(5)
        assert not chosen.eligible_for_election()


class TestCancellation:
    def test_cancel_leaves_the_original_untouched(self):
        chosen = move()
        chosen.advance(4)
        verdict = chosen.cancel()
        assert "the original on b1 is untouched" in verdict
        assert "never coverage" in verdict

    def test_advancing_a_cancelled_move_is_refused(self):
        chosen = move()
        chosen.cancel()
        with pytest.raises(Invalid):
            chosen.advance(1)
