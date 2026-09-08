from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.groupgeneration import GroupGeneration


class TestRebalance:
    def test_a_rebalance_bumps_the_generation(self):
        g = GroupGeneration()
        assert g.rebalance("member joined") == 1
        assert g.rebalance("member left") == 2

    def test_the_reason_is_recorded(self):
        g = GroupGeneration()
        g.rebalance("heartbeat lapsed")
        assert "heartbeat lapsed" in g.note()


class TestAdmit:
    def test_a_current_generation_is_admitted(self):
        g = GroupGeneration()
        g.rebalance("join")
        assert "admitted" in g.admit(1, "commit")

    def test_a_stale_generation_is_rejected(self):
        g = GroupGeneration()
        g.rebalance("join")
        g.rebalance("rejoin")  # now at generation 2
        with pytest.raises(Invalid) as caught:
            g.admit(1, "commit")  # a member still on generation 1
        assert "illegal-generation" in str(caught.value)
        assert "must rejoin" in str(caught.value)

    def test_a_future_generation_is_rejected(self):
        g = GroupGeneration()
        g.rebalance("join")
        with pytest.raises(Invalid) as caught:
            g.admit(5, "heartbeat")  # ahead of the coordinator
        assert "cannot legitimately exist" in str(caught.value)

    def test_the_initial_generation_admits_generation_zero(self):
        g = GroupGeneration()
        assert "admitted" in g.admit(0, "heartbeat")


class TestNote:
    def test_the_note_states_the_current_generation(self):
        g = GroupGeneration()
        g.rebalance("join")
        assert "generation 1" in g.note()
