from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.produceracks import ProducerAcks


class TestWaitsFor:
    def test_acks_zero_waits_for_nothing(self):
        assert "fire and forget" in ProducerAcks("0").waits_for()

    def test_acks_one_waits_for_the_leader(self):
        assert "leader" in ProducerAcks("1").waits_for()

    def test_acks_all_waits_for_every_in_sync_replica(self):
        assert "every in-sync replica" in ProducerAcks("all").waits_for()


class TestLoss:
    def test_acks_zero_loses_on_any_failure(self):
        assert ProducerAcks("0").loses_record(leader_fails_before_replication=False)

    def test_acks_one_loses_when_the_leader_fails_before_replication(self):
        a = ProducerAcks("1")
        assert a.loses_record(leader_fails_before_replication=True)
        assert not a.loses_record(leader_fails_before_replication=False)

    def test_acks_all_survives_a_leader_failure(self):
        a = ProducerAcks("all")
        assert not a.loses_record(leader_fails_before_replication=True)


class TestRefusal:
    def test_an_unknown_level_is_refused(self):
        with pytest.raises(Invalid) as caught:
            ProducerAcks("2")
        assert "not one of 0, 1, all" in str(caught.value)


class TestNote:
    def test_the_note_names_the_min_in_sync_pairing(self):
        note = ProducerAcks("all").note()
        assert "min-in-sync floor" in note

    def test_the_note_states_the_wait_and_loss(self):
        note = ProducerAcks("1").note()
        assert "waits for" in note
        assert "loses on" in note
