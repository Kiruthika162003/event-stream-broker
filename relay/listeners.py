"""Listeners: client traffic and broker traffic ride separate doors on purpose.

A broker opens more than one listener, each a name, host, and port
with its own security, because client traffic and inter-broker
traffic have different needs and different trust. The inter-broker
listener carries replication and controller messages between
brokers inside the cluster, often on a private network with mutual
authentication, while the client listener carries produce and fetch
from applications, often reachable more widely and authenticated
differently. Keeping them separate lets an operator firewall the
inter-broker port to cluster members only and expose just the
client port, so a compromised client cannot even reach the
replication protocol. The router enforces the separation by request
kind: a replication or controller request arriving on the client
listener is rejected, because a client speaking the inter-broker
protocol is either misconfigured or probing, and an ordinary
produce arriving on the inter-broker listener is rejected too,
because client traffic on the private door defeats the firewalling
the separation was for. The advertised address matters as much as
the bound one: a broker binds a listener to a local interface but
advertises the address other brokers and clients should connect
back on, and the two differ behind NAT or in a container, so the
router refuses to advertise an empty address, which would tell
peers to connect to nothing. The report states which listener
serves which protocol, because a connection failing to reach a
broker is often a client pointed at the inter-broker port or a
peer pointed at the client one, and naming the mapping turns a
mysterious timeout into an obvious misconfiguration.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid

CLIENT = "client"
INTERBROKER = "interbroker"
_CLIENT_PROTOCOLS = ("produce", "fetch", "metadata", "offsetcommit")
_INTERBROKER_PROTOCOLS = ("replicate", "controller", "leaderandisr")


@dataclass
class Listener:
    name: str
    role: str
    advertised: str

    def __post_init__(self) -> None:
        if self.role not in (CLIENT, INTERBROKER):
            raise Invalid(f"unknown listener role '{self.role}'")
        if not self.advertised:
            raise Invalid(
                "a listener must advertise an address; an empty one "
                "tells peers to connect to nothing"
            )


@dataclass
class ListenerRouter:
    listeners: dict[str, Listener] = field(default_factory=dict)

    def add(self, listener: Listener) -> None:
        self.listeners[listener.role] = listener

    def route(self, arrived_on: str, protocol: str) -> str:
        listener = self.listeners.get(arrived_on)
        if listener is None:
            raise Invalid(f"no listener for role '{arrived_on}'")
        if arrived_on == CLIENT and protocol in _INTERBROKER_PROTOCOLS:
            raise Invalid(
                f"'{protocol}' is an inter-broker protocol arriving "
                "on the client listener; a client speaking it is "
                "misconfigured or probing"
            )
        if arrived_on == INTERBROKER and protocol in _CLIENT_PROTOCOLS:
            raise Invalid(
                f"'{protocol}' is client traffic on the private "
                "inter-broker door; that defeats the firewalling the "
                "separation exists for"
            )
        return f"'{protocol}' served on the {arrived_on} listener"

    def mapping(self) -> str:
        parts = [
            f"{role} -> {lis.advertised}"
            for role, lis in sorted(self.listeners.items())
        ]
        return (
            "; ".join(parts)
            + "; a timeout is often a peer pointed at the wrong door"
        )
