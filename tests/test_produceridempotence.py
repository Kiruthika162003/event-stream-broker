from __future__ import annotations

import pytest

from relay.errors import Fenced, Invalid
from relay.produceridempotence import ProducerIdempotence


class TestFirstBatch:
    def test_the_first_batch_starts_at_zero(self):
        p = ProducerIdempotence()
        assert "first batch" in p.accept("p1", 0, epoch=0, sequence=0)

    def test_a_first_batch_not_at_zero_is_refused(self):
        p = ProducerIdempotence()
        with pytest.raises(Invalid) as caught:
            p.accept("p1", 0, epoch=0, sequence=3)
        assert "lost" in str(caught.value)


class TestSequence:
    def test_the_next_sequence_is_accepted(self):
        p = ProducerIdempotence()
        p.accept("p1", 0, epoch=0, sequence=0)
        assert p.accept("p1", 0, epoch=0, sequence=1) == "accepted"

    def test_a_replayed_sequence_is_a_harmless_duplicate(self):
        p = ProducerIdempotence()
        p.accept("p1", 0, epoch=0, sequence=0)
        p.accept("p1", 0, epoch=0, sequence=1)
        note = p.accept("p1", 0, epoch=0, sequence=1)  # the timed-out retry
        assert "duplicate" in note

    def test_an_out_of_order_gap_is_refused(self):
        p = ProducerIdempotence()
        p.accept("p1", 0, epoch=0, sequence=0)
        with pytest.raises(Invalid) as caught:
            p.accept("p1", 0, epoch=0, sequence=5)
        assert "gap" in str(caught.value)

    def test_each_partition_tracks_its_own_sequence(self):
        p = ProducerIdempotence()
        p.accept("p1", 0, epoch=0, sequence=0)
        # partition 1 starts fresh, not continuing partition 0
        assert "first batch" in p.accept("p1", 1, epoch=0, sequence=0)


class TestEpoch:
    def test_a_zombie_epoch_is_fenced(self):
        p = ProducerIdempotence()
        p.accept("p1", 0, epoch=5, sequence=0)
        with pytest.raises(Fenced) as caught:
            p.accept("p1", 0, epoch=4, sequence=1)  # old instance still writing
        assert "zombie" in str(caught.value)

    def test_a_new_epoch_resets_the_sequence(self):
        p = ProducerIdempotence()
        p.accept("p1", 0, epoch=0, sequence=0)
        p.accept("p1", 0, epoch=0, sequence=1)
        # the producer restarted with a bumped epoch
        assert "new epoch" in p.accept("p1", 0, epoch=1, sequence=0)


class TestState:
    def test_the_high_sequence_is_reported(self):
        p = ProducerIdempotence()
        p.accept("p1", 0, epoch=0, sequence=0)
        p.accept("p1", 0, epoch=0, sequence=1)
        assert p.high_sequence("p1", 0) == 1

    def test_an_unknown_producer_has_no_high_sequence(self):
        with pytest.raises(Invalid):
            ProducerIdempotence().high_sequence("nobody", 0)

    def test_the_note_counts_tracked_pairs(self):
        p = ProducerIdempotence()
        p.accept("p1", 0, epoch=0, sequence=0)
        p.accept("p2", 0, epoch=0, sequence=0)
        assert "2 producer" in p.note()
