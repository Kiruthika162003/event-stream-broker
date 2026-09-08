from __future__ import annotations

import pytest

from relay.causaldelivery import CausalDelivery
from relay.errors import Invalid


class TestDelivery:
    def test_a_message_with_no_deps_delivers_immediately(self):
        d = CausalDelivery()
        assert d.accept("m1", set()) == ["m1"]

    def test_a_message_waits_for_its_dependency(self):
        d = CausalDelivery()
        # m2 depends on m1, but m1 not delivered yet
        assert d.accept("m2", {"m1"}) == []
        assert "m2" not in d.delivered

    def test_delivering_a_cause_releases_the_waiting_effect(self):
        d = CausalDelivery()
        d.accept("m2", {"m1"})  # buffered
        released = d.accept("m1", set())  # cause arrives
        assert "m1" in released
        assert "m2" in released

    def test_release_cascades_through_a_chain(self):
        d = CausalDelivery()
        d.accept("m3", {"m2"})  # buffered
        d.accept("m2", {"m1"})  # buffered
        released = d.accept("m1", set())
        assert set(released) == {"m1", "m2", "m3"}


class TestForce:
    def test_force_delivering_with_unmet_deps_is_refused(self):
        d = CausalDelivery()
        with pytest.raises(Invalid) as caught:
            d.force_deliver("m2", {"m1"})
        assert "before its cause" in str(caught.value)


class TestBuffered:
    def test_buffered_note_counts_waiting(self):
        d = CausalDelivery()
        d.accept("m2", {"m1"})
        assert "1 message(s) buffered" in d.buffered_note()
