from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.produceridexpiry import ProducerRegistry, ProducerState


class TestExpireIdle:
    def test_a_producer_idle_past_the_timeout_is_expired(self):
        reg = ProducerRegistry(timeout_ticks=100)
        reg.track(ProducerState(producer_id=1, last_seq=5, idle_ticks=150))
        reg.track(ProducerState(producer_id=2, last_seq=9, idle_ticks=10))
        expired = reg.expire_idle()
        assert expired == [1]
        assert 2 in reg.states

    def test_an_idle_producer_in_a_transaction_is_not_expired(self):
        reg = ProducerRegistry(timeout_ticks=100)
        reg.track(
            ProducerState(
                producer_id=1,
                last_seq=5,
                idle_ticks=150,
                in_transaction=True,
            )
        )
        with pytest.raises(Invalid) as caught:
            reg.expire_idle()
        assert "strand the transaction" in str(caught.value)

    def test_a_bad_timeout_is_refused(self):
        with pytest.raises(Invalid):
            ProducerRegistry(timeout_ticks=0)


class TestResumeNote:
    def test_a_tracked_producer_resumes(self):
        reg = ProducerRegistry(timeout_ticks=100)
        reg.track(ProducerState(producer_id=1, last_seq=5, idle_ticks=10))
        assert "dedup still holds" in reg.resume_note(1)

    def test_an_expired_producer_must_reinitialize(self):
        reg = ProducerRegistry(timeout_ticks=100)
        note = reg.resume_note(99)
        assert "must re-initialize" in note
        assert "new producer id" in note


class TestLiveVersusExpirable:
    def test_it_counts_live_against_idle(self):
        reg = ProducerRegistry(timeout_ticks=100)
        reg.track(ProducerState(producer_id=1, last_seq=5, idle_ticks=10))
        reg.track(ProducerState(producer_id=2, last_seq=9, idle_ticks=150))
        note = reg.live_versus_expirable()
        assert "1 live producer(s), 1 idle" in note
