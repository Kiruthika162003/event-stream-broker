from __future__ import annotations

import pytest

from relay.errors import Fenced, Invalid
from relay.heartbeatsignal import ACK, REBALANCE, HeartbeatCoordinator


def _coord():
    c = HeartbeatCoordinator(generation=5)
    c.register("m1")
    return c


class TestStable:
    def test_a_stable_group_acknowledges(self):
        assert _coord().heartbeat("m1", member_generation=5) == ACK


class TestRebalance:
    def test_a_rebalance_is_signalled_in_the_reply(self):
        c = _coord()
        c.start_rebalance()
        assert c.heartbeat("m1", member_generation=5) == REBALANCE

    def test_completing_a_rebalance_bumps_the_generation(self):
        c = _coord()
        c.start_rebalance()
        c.complete_rebalance()
        assert c.generation == 6
        # the member rejoined at 6 and now gets a plain ack
        assert c.heartbeat("m1", member_generation=6) == ACK


class TestFencing:
    def test_a_stale_generation_is_fenced(self):
        c = _coord()
        c.start_rebalance()
        c.complete_rebalance()
        with pytest.raises(Fenced) as caught:
            c.heartbeat("m1", member_generation=5)
        assert "double-owner" in str(caught.value)

    def test_an_unknown_member_is_refused(self):
        c = _coord()
        with pytest.raises(Invalid) as caught:
            c.heartbeat("ghost", member_generation=5)
        assert "not a known member" in str(caught.value)
