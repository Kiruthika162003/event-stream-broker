from __future__ import annotations

import pytest

from relay.becomeleader import LeaderTransition
from relay.errors import Invalid, Missing


class TestBecomeLeader:
    def test_the_transition_stops_fetching_and_serves(self):
        t = LeaderTransition(hosts=True, epoch=5)
        note = t.become_leader(new_epoch=6, isr_end_offsets=[100, 98, 100])
        assert "fetcher stopped" in note
        assert "watermark set to 98" in note
        assert not t.fetching
        assert t.serving

    def test_a_partition_not_hosted_is_refused(self):
        t = LeaderTransition(hosts=False)
        with pytest.raises(Missing):
            t.become_leader(new_epoch=1, isr_end_offsets=[0])

    def test_a_non_advancing_epoch_is_refused(self):
        t = LeaderTransition(hosts=True, epoch=5)
        with pytest.raises(Invalid) as caught:
            t.become_leader(new_epoch=5, isr_end_offsets=[0])
        assert "epochs only advance" in str(caught.value)


class TestAcceptProduce:
    def test_produce_before_the_transition_is_refused(self):
        t = LeaderTransition(hosts=True)
        with pytest.raises(Invalid) as caught:
            t.accept_produce("r")
        assert "transition is not" in str(caught.value)

    def test_produce_after_the_transition_is_accepted(self):
        t = LeaderTransition(hosts=True, epoch=5)
        t.become_leader(new_epoch=6, isr_end_offsets=[10])
        assert "produced 'r' at epoch 6" in t.accept_produce("r")
