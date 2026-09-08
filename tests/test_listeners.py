from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.listeners import (
    CLIENT,
    INTERBROKER,
    Listener,
    ListenerRouter,
)


def _router():
    r = ListenerRouter()
    r.add(Listener("EXTERNAL", CLIENT, advertised="broker1.example:9092"))
    r.add(Listener("INTERNAL", INTERBROKER, advertised="10.0.0.1:9094"))
    return r


class TestListener:
    def test_an_unknown_role_is_refused(self):
        with pytest.raises(Invalid):
            Listener("X", "gossip", advertised="host:1")

    def test_an_empty_advertised_address_is_refused(self):
        with pytest.raises(Invalid) as caught:
            Listener("X", CLIENT, advertised="")
        assert "connect to nothing" in str(caught.value)


class TestRoute:
    def test_client_traffic_on_the_client_listener_is_served(self):
        assert "served on the client" in _router().route(CLIENT, "produce")

    def test_replication_on_the_interbroker_listener_is_served(self):
        assert "served on the interbroker" in _router().route(
            INTERBROKER, "replicate"
        )

    def test_interbroker_protocol_on_the_client_door_is_refused(self):
        with pytest.raises(Invalid) as caught:
            _router().route(CLIENT, "controller")
        assert "misconfigured or probing" in str(caught.value)

    def test_client_traffic_on_the_private_door_is_refused(self):
        with pytest.raises(Invalid) as caught:
            _router().route(INTERBROKER, "produce")
        assert "defeats the firewalling" in str(caught.value)


class TestMapping:
    def test_the_mapping_names_each_door(self):
        note = _router().mapping()
        assert "client -> broker1.example:9092" in note
        assert "interbroker -> 10.0.0.1:9094" in note
