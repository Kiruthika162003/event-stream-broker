from __future__ import annotations

import pytest

from relay.coordinatorepoch import CoordinatorEpoch
from relay.errors import Fenced, Invalid


class TestWrite:
    def test_a_write_at_the_current_epoch_is_accepted(self):
        c = CoordinatorEpoch(epoch=3)
        assert "accepted" in c.write(3, "commit t1")

    def test_a_write_below_the_current_epoch_is_fenced(self):
        c = CoordinatorEpoch(epoch=3)
        with pytest.raises(Fenced) as caught:
            c.write(2, "commit t1")  # from a superseded coordinator
        assert "superseded" in str(caught.value)

    def test_a_write_above_the_current_epoch_is_accepted(self):
        # a write at a higher epoch is from a coordinator that took over
        c = CoordinatorEpoch(epoch=3)
        assert "accepted" in c.write(5, "commit t1")


class TestTakeover:
    def test_takeover_bumps_the_epoch(self):
        c = CoordinatorEpoch(epoch=3)
        c.take_over(4)
        assert c.epoch == 4

    def test_the_old_coordinator_is_fenced_after_takeover(self):
        c = CoordinatorEpoch(epoch=3)
        c.take_over(4)
        with pytest.raises(Fenced):
            c.write(3, "abort t1")  # the old coordinator's next write

    def test_a_backwards_takeover_is_refused(self):
        c = CoordinatorEpoch(epoch=3)
        with pytest.raises(Invalid) as caught:
            c.take_over(2)
        assert "reopen the fence" in str(caught.value)

    def test_a_takeover_at_the_same_epoch_is_refused(self):
        c = CoordinatorEpoch(epoch=3)
        with pytest.raises(Invalid):
            c.take_over(3)


class TestCount:
    def test_fenced_writes_are_counted(self):
        c = CoordinatorEpoch(epoch=3)
        for _ in range(2):
            with pytest.raises(Fenced):
                c.write(1, "zombie write")
        assert c.fenced_count() == 2

    def test_the_note_states_the_epoch_and_fenced_count(self):
        c = CoordinatorEpoch(epoch=5)
        assert "epoch 5" in c.note()
