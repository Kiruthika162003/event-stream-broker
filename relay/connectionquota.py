"""Connection quota: one host cannot open every socket the broker has.

A broker can hold only so many open connections, bounded by file
descriptors and memory per connection, and without a limit a single
misbehaving client, a reconnect storm from one bad deploy, can open
connections until the broker runs out and cannot accept anyone,
including healthy clients and other brokers. The connection quota
puts two caps in front of that. A per-IP cap stops any single host
from opening more than its share, so one client's storm is
contained to that client rather than starving the whole broker, and
a broker-wide cap stops the sum of all clients from exhausting the
descriptors even when no single one is over its per-IP share. The
per-IP cap is checked first and is the one that usually fires,
because a reconnect storm comes from one place, and rejecting its
excess connections while accepting others is exactly the isolation
the cap is for. The limiter refuses a new connection that would put
a host over its per-IP cap and refuses one that would put the
broker over its total even if the host is under its own cap, and it
distinguishes the two in the rejection, because a client told it
hit the broker-wide limit knows the broker is saturated overall
while one told it hit its per-IP limit knows it alone is the
problem. A listener reserved for inter-broker traffic is exempt
from the client per-IP cap, because starving replication to enforce
a client limit would break the cluster to protect it. The report
states the busiest host's share of the broker's connections,
because a single host holding most of them is the reconnect storm
to chase before the broker saturates.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class ConnectionQuota:
    per_ip_cap: int
    broker_cap: int
    counts: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.per_ip_cap < 1 or self.broker_cap < 1:
            raise Invalid("both caps must be positive")

    def total(self) -> int:
        return sum(self.counts.values())

    def open(self, host: str, interbroker: bool = False) -> str:
        if self.total() >= self.broker_cap:
            raise Invalid(
                f"broker-wide cap {self.broker_cap} reached; the "
                "broker is saturated overall, not just this host"
            )
        if not interbroker and self.counts.get(host, 0) >= self.per_ip_cap:
            raise Invalid(
                f"host {host} is at its per-IP cap {self.per_ip_cap}; "
                "this host alone is the problem, a reconnect storm "
                "contained rather than starving the broker"
            )
        self.counts[host] = self.counts.get(host, 0) + 1
        return f"accepted from {host}; {self.total()}/{self.broker_cap} total"

    def close(self, host: str) -> None:
        if self.counts.get(host, 0) > 0:
            self.counts[host] -= 1
            if self.counts[host] == 0:
                del self.counts[host]

    def busiest(self) -> str:
        if not self.counts:
            return "no connections open"
        host = max(self.counts, key=self.counts.get)
        share = self.counts[host] / self.total() * 100
        return (
            f"{host} holds {self.counts[host]}/{self.total()} "
            f"({share:.0f}%); a host holding most is the reconnect "
            "storm to chase before saturation"
        )
