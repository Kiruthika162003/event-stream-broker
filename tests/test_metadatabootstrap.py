from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.metadatabootstrap import Bootstrapper


class TestFetch:
    def test_the_first_reachable_broker_bootstraps(self):
        b = Bootstrapper(
            bootstrap=["b1", "b2", "b3"],
            reachable={"b1", "b2"},
        )
        assert "from 'b1' after trying 1 broker(s)" in b.fetch_metadata()

    def test_it_falls_through_to_a_later_reachable_broker(self):
        b = Bootstrapper(
            bootstrap=["b1", "b2", "b3"],
            reachable={"b3"},
        )
        assert "after trying 3 broker(s)" in b.fetch_metadata()

    def test_no_reachable_broker_fails_startup(self):
        b = Bootstrapper(bootstrap=["b1"], reachable=set())
        with pytest.raises(Invalid) as caught:
            b.fetch_metadata()
        assert "cannot start" in str(caught.value)

    def test_an_empty_bootstrap_list_is_refused(self):
        with pytest.raises(Invalid):
            Bootstrapper(bootstrap=[])


class TestRouting:
    def test_routing_before_metadata_is_refused(self):
        b = Bootstrapper(bootstrap=["b1"], reachable={"b1"})
        with pytest.raises(Invalid) as caught:
            b.leader_of(0)
        assert "before metadata is fetched" in str(caught.value)

    def test_routing_after_metadata_returns_the_leader(self):
        b = Bootstrapper(
            bootstrap=["b1"],
            reachable={"b1"},
            leaders={0: "b7"},
        )
        b.fetch_metadata()
        assert b.leader_of(0) == "b7"


class TestTries:
    def test_first_broker_answering_is_healthy(self):
        b = Bootstrapper(bootstrap=["b1", "b2"], reachable={"b1"})
        assert "healthy" in b.tries_needed()

    def test_falling_through_is_a_fragility(self):
        b = Bootstrapper(bootstrap=["b1", "b2", "b3"], reachable={"b3"})
        assert "fell through 2 down broker(s)" in b.tries_needed()
