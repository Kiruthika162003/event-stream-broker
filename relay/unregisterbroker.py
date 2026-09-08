"""Unregister broker: a broker leaves only after its data has somewhere else to be.

Removing a broker from the cluster for good, a decommission, is not
just deleting its registration, because the broker holds partition
replicas and leads some partitions, and pulling it out while it
still matters loses data or availability. The order that makes a
decommission safe is: first move every partition this broker leads
to another leader, so no client is talking to it as a leader when
it goes, then reassign every replica it hosts to other brokers and
wait for those new replicas to catch up into the in-sync set, so
the redundancy the departing broker provided is restored elsewhere,
and only then unregister it. Skipping the replica reassignment is
the dangerous shortcut: unregistering a broker that still holds the
only in-sync copy of a partition, or a copy the cluster was
counting toward its replication factor, drops the cluster below the
redundancy it promised, and if another broker then fails the
partition is lost. The manager enforces the order, refusing to
unregister a broker that still leads any partition, naming them so
leadership can be moved first, and refusing one that still hosts
replicas the cluster needs, distinguishing a replica already
re-homed elsewhere from one whose removal would drop a partition
below its minimum in-sync count. It allows unregistering a broker
that leads nothing and hosts only replicas already replaced, the
clean case, and reports what still blocks the decommission, because
a decommission that hangs is usually one partition whose
reassignment has not finished catching up, and naming it turns an
opaque wait into a specific thing to watch.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class Decommission:
    broker: str
    leads: set[str] = field(default_factory=set)
    hosts_needed: set[str] = field(default_factory=set)

    def leadership_moved(self, partition: str) -> None:
        self.leads.discard(partition)

    def replica_rehomed(self, partition: str) -> None:
        self.hosts_needed.discard(partition)

    def can_unregister(self) -> bool:
        return not self.leads and not self.hosts_needed

    def unregister(self) -> str:
        if self.leads:
            raise Invalid(
                f"broker '{self.broker}' still leads {sorted(self.leads)}; "
                "move leadership first so no client is talking to it as "
                "leader when it goes"
            )
        if self.hosts_needed:
            raise Invalid(
                f"broker '{self.broker}' still hosts needed replicas "
                f"{sorted(self.hosts_needed)}; reassign and let them catch "
                "up first, or the cluster drops below its replication factor"
            )
        return f"unregistered '{self.broker}'; it led nothing and hosted no needed replica"

    def blockers(self) -> str:
        if self.can_unregister():
            return "nothing blocks the decommission; safe to unregister"
        return (
            f"blocked: leads {sorted(self.leads)}, hosts needed "
            f"{sorted(self.hosts_needed)}; a hang here is usually a "
            "reassignment still catching up"
        )
