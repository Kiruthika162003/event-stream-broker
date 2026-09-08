from __future__ import annotations

import pytest

from relay.brokerid import BrokerRegistry
from relay.errors import Invalid


def registry() -> BrokerRegistry:
    r = BrokerRegistry()
    r.register(5, "incarnation-a", previous_alive=False)
    return r


class TestRegistration:
    def test_a_fresh_id_registers(self):
        r = BrokerRegistry()
        assert "registered" in r.register(
            1, "inc-1", previous_alive=False
        )

    def test_a_live_conflict_is_refused(self):
        r = registry()
        with pytest.raises(Invalid) as caught:
            r.register(5, "incarnation-b", previous_alive=True)
        assert "conflict" in str(caught.value)
        assert "Find the cloned config" in str(caught.value)

    def test_a_restart_of_a_dead_broker_is_welcomed(self):
        r = registry()
        verdict = r.register(
            5, "incarnation-b", previous_alive=False
        )
        assert "legitimate restart" in verdict

    def test_the_same_incarnation_re_registering_is_fine(self):
        r = registry()
        verdict = r.register(
            5, "incarnation-a", previous_alive=True
        )
        assert "registered" in verdict


class TestConflictCheck:
    def test_is_conflict_detects_the_duplicate(self):
        r = registry()
        assert r.is_conflict(5, "incarnation-b", previous_alive=True)

    def test_is_conflict_clears_a_restart(self):
        r = registry()
        assert not r.is_conflict(
            5, "incarnation-b", previous_alive=False
        )

    def test_deregister_frees_the_id(self):
        r = registry()
        r.deregister(5)
        assert "registered" in r.register(
            5, "incarnation-c", previous_alive=False
        )
