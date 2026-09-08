"""The controller: one broker owns the metadata, and its version is law.

Some decisions must be made by exactly one broker, or the
cluster forks: which broker leads each partition, which
partitions exist, which replicas are in-sync. The controller is
that single decision-maker, elected among the brokers, and its
output is a metadata snapshot with a monotonic version. Every
broker caches the metadata and stamps its requests with the
version it holds, so the controller can detect a broker acting
on a stale view and tell it to refresh rather than letting it
route to a leader that moved. The controller epoch fences a
deposed controller exactly as a partition epoch fences a
deposed leader: a metadata update from an old controller epoch
is rejected, because two brokers both believing they are the
controller is the cluster-level split brain, the one that
reassigns the same partition two different ways. Metadata
propagation is push-on-change plus pull-on-miss, never a
periodic full sync, because a cluster that only learns the
truth on a timer is a cluster that routes to dead leaders for
the length of the timer.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Fenced, Invalid


@dataclass
class Metadata:
    version: int
    leaders: dict[int, str]

    def leader_of(self, partition: int) -> str:
        leader = self.leaders.get(partition)
        if leader is None:
            raise Invalid(f"partition {partition} has no leader")
        return leader


@dataclass
class Controller:
    controller_epoch: int
    metadata: Metadata
    updates_applied: int = 0
    stale_routes_caught: int = 0

    def update_leader(
        self, epoch: int, partition: int, leader: str
    ) -> str:
        if epoch < self.controller_epoch:
            raise Fenced(
                f"metadata update from controller epoch {epoch} "
                f"rejected; the current controller is at "
                f"{self.controller_epoch}, and two controllers "
                "is the cluster-level split brain"
            )
        self.metadata = Metadata(
            version=self.metadata.version + 1,
            leaders={**self.metadata.leaders, partition: leader},
        )
        self.updates_applied += 1
        return (
            f"partition {partition} leader is {leader}, metadata "
            f"version {self.metadata.version}"
        )

    def route(
        self, broker_cached_version: int, partition: int
    ) -> str:
        if broker_cached_version < self.metadata.version:
            self.stale_routes_caught += 1
            raise Invalid(
                f"broker holds metadata version "
                f"{broker_cached_version}, current is "
                f"{self.metadata.version}; refresh before "
                "routing, or route to a leader that moved"
            )
        return self.metadata.leader_of(partition)

    def report(self) -> str:
        return (
            f"controller epoch {self.controller_epoch}, metadata "
            f"version {self.metadata.version}, "
            f"{self.updates_applied} update(s), "
            f"{self.stale_routes_caught} stale route(s) caught "
            "before they reached a dead leader"
        )
