"""Cluster membership: brokers join, heartbeat, and leave without a vote.

A cluster is a set of brokers that agree on who is in the set,
and the agreement is maintained by registration and heartbeat
rather than by asking every broker's opinion, which would not
converge under the partitions membership exists to survive. A
broker registers with an id and a rack, heartbeats to stay
alive, and is fenced when its heartbeat lapses, its
partition-leaderships freed for reassignment. The rack is not
decoration: it lets the placement layer keep a partition's
replicas in different racks so one rack's power failure cannot
take a majority, and a cluster that ignores racks discovers
during the outage that its three replicas shared one switch.
The membership epoch increments on every join and fence so that
stale views are detectable, and the fence is deliberately
slower than a single missed heartbeat, because fencing a broker
that was busy for a moment triggers a reassignment storm that
costs more than the brief unavailability it was trying to avoid.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid, Missing


@dataclass
class Broker:
    broker_id: str
    rack: str
    last_heartbeat: int
    fenced: bool = False


@dataclass
class ClusterMembership:
    fence_after: int
    brokers: dict[str, Broker] = field(default_factory=dict)
    epoch: int = 0

    def __post_init__(self) -> None:
        if self.fence_after < 1:
            raise Invalid("the fence timeout must be positive")

    def register(
        self, broker_id: str, rack: str, now: int
    ) -> str:
        self.epoch += 1
        self.brokers[broker_id] = Broker(
            broker_id=broker_id, rack=rack, last_heartbeat=now
        )
        return (
            f"{broker_id} joined rack {rack} at epoch "
            f"{self.epoch}"
        )

    def heartbeat(self, broker_id: str, now: int) -> None:
        broker = self.brokers.get(broker_id)
        if broker is None:
            raise Missing(f"{broker_id} is not registered")
        if broker.fenced:
            raise Invalid(
                f"{broker_id} was fenced and must re-register, "
                "not resume, or the cluster holds two views of it"
            )
        broker.last_heartbeat = now

    def fence_lapsed(self, now: int) -> list[str]:
        fenced = []
        for broker in self.brokers.values():
            if broker.fenced:
                continue
            if now - broker.last_heartbeat > self.fence_after:
                broker.fenced = True
                fenced.append(broker.broker_id)
        if fenced:
            self.epoch += 1
        return sorted(fenced)

    def live_brokers(self) -> list[str]:
        return sorted(
            b.broker_id
            for b in self.brokers.values()
            if not b.fenced
        )

    def racks_available(self) -> set[str]:
        return {
            b.rack
            for b in self.brokers.values()
            if not b.fenced
        }

    def rack_diverse_enough(self, replication_factor: int) -> str:
        racks = self.racks_available()
        if len(racks) >= replication_factor:
            return (
                f"{len(racks)} rack(s) for a factor of "
                f"{replication_factor}: replicas can span racks "
                "so one power failure cannot take a majority"
            )
        return (
            f"only {len(racks)} rack(s) for a factor of "
            f"{replication_factor}: some replicas must share a "
            "rack, and that shared switch is the outage waiting "
            "to happen"
        )
