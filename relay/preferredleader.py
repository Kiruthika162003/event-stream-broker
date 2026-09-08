"""Preferred leaders: failovers pile leadership, and balance must be restored.

Each partition has a preferred leader, the first broker in its
replica list, chosen so that when every partition leads on its
preferred broker, leadership is spread evenly across the cluster.
Failovers erode this: when a broker dies its partitions fail over
to survivors, and when it returns it is a follower again, so
after a few failovers the surviving brokers carry double
leadership while the returned one carries none, and the cluster
is balanced in replicas but lopsided in the work of being leader,
which is where the produce and fetch traffic actually lands.
Preferred leader election moves each partition's leadership back
to its preferred broker once that broker is caught up, restoring
the even spread. The move is only safe when the preferred broker
is in-sync, because handing leadership to a broker still catching
up would stall the partition, so the checker refuses a premature
switch. The imbalance is measured as the spread between the
busiest and idlest broker's leader count, because that spread,
not the average, is what determines whether one broker is a
hotspot while another idles, and a cluster balanced on average
can still have a broker melting.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class LeadershipBalance:
    preferred: dict[int, str]
    current_leader: dict[int, str]
    in_sync: dict[int, set[str]] = field(default_factory=dict)

    def leader_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for leader in self.current_leader.values():
            counts[leader] = counts.get(leader, 0) + 1
        return counts

    def imbalance(self) -> int:
        counts = self.leader_counts()
        if not counts:
            return 0
        return max(counts.values()) - min(counts.values())

    def restorable(self) -> list[int]:
        restorable = []
        for partition, preferred in self.preferred.items():
            if self.current_leader.get(partition) == preferred:
                continue
            if preferred in self.in_sync.get(partition, set()):
                restorable.append(partition)
        return sorted(restorable)

    def restore(self, partition: int) -> str:
        preferred = self.preferred.get(partition)
        if preferred is None:
            raise Invalid(f"partition {partition} has no preferred")
        if self.current_leader.get(partition) == preferred:
            return f"partition {partition} already on its preferred"
        if preferred not in self.in_sync.get(partition, set()):
            raise Invalid(
                f"partition {partition} preferred leader "
                f"{preferred} is not in-sync; switching now "
                "would stall the partition while it catches up"
            )
        self.current_leader[partition] = preferred
        return (
            f"partition {partition} leadership restored to "
            f"{preferred}"
        )

    def report(self) -> str:
        counts = self.leader_counts()
        spread = self.imbalance()
        if spread <= 1:
            return (
                f"leadership balanced (spread {spread}); no "
                "broker is a hotspot"
            )
        busiest = max(counts, key=lambda b: counts[b])
        idlest = min(counts, key=lambda b: counts[b])
        return (
            f"spread {spread}: {busiest} leads "
            f"{counts[busiest]} while {idlest} leads "
            f"{counts[idlest]}; the average would hide that one "
            "broker is melting"
        )
