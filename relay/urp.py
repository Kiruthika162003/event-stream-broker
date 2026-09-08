"""Under-replicated partitions: the number that measures how close to loss.

A partition's replication factor is its promise; its in-sync
count is its reality, and the gap between them is the single best
predictor of imminent data loss. A partition with factor three
and three in-sync can lose two brokers and survive; the same
partition with only one in-sync is one failure from unavailability
and two from loss, while looking identical on a dashboard that
shows only the leader. The monitor computes each partition's
margin, in-sync minus the minimum required, and classifies:
healthy has margin to spare, at-risk is at the minimum with no
slack, and under-minimum is already below the floor and therefore
not accepting acks-all writes. The cluster-level number that
matters is the count of at-risk-or-worse partitions, because that
is the blast radius of the next broker failure, and a cluster
reporting zero under-replicated partitions is a cluster where a
broker can die with no data-loss exposure, which is the only
state worth calling healthy. The monitor refuses to average the
margin across partitions, because one partition at margin minus
two is an emergency that an average with ninety-nine healthy
partitions hides completely.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class PartitionReplication:
    partition: int
    replication_factor: int
    in_sync: int
    min_in_sync: int

    def __post_init__(self) -> None:
        if self.in_sync > self.replication_factor:
            raise Invalid(
                "in-sync above the replication factor is "
                "impossible"
            )

    def margin(self) -> int:
        return self.in_sync - self.min_in_sync

    def state(self) -> str:
        if self.in_sync < self.min_in_sync:
            return "under-minimum"
        if self.margin() == 0:
            return "at-risk"
        return "healthy"


@dataclass
class ReplicationMonitor:
    partitions: list[PartitionReplication]

    def under_replicated(self) -> list[PartitionReplication]:
        return [
            p
            for p in self.partitions
            if p.in_sync < p.replication_factor
        ]

    def at_risk_or_worse(self) -> list[int]:
        return sorted(
            p.partition
            for p in self.partitions
            if p.state() != "healthy"
        )

    def blast_radius(self) -> str:
        if not self.partitions:
            raise Invalid("no partitions to monitor")
        exposed = self.at_risk_or_worse()
        if not exposed:
            return (
                "0 partition(s) at risk; a broker can die with "
                "no data-loss exposure, the only state worth "
                "calling healthy"
            )
        worst = min(p.margin() for p in self.partitions)
        return (
            f"{len(exposed)} partition(s) at risk or worse "
            f"(worst margin {worst}); this is the blast radius "
            "of the next broker failure, never averaged away"
        )
