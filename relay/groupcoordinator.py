"""Group coordinator: which broker owns a group, computed not looked up.

Every consumer group needs one broker to coordinate it, to run
its rebalances and hold its committed offsets, and a client must
find that broker before it can join. The elegant answer avoids a
lookup service: the coordinator for a group is the leader of the
offset-store partition that the group's name hashes to, so any
client can compute which partition holds a group and then ask
metadata for that partition's leader, no separate registry to
keep consistent. This reuse is the same trick the offset store
uses, group progress living in the log, extended to coordination
itself: the machinery that assigns partition leadership already
assigns group coordination, and there is no second election to
get wrong. When the coordinating broker fails, the offset-store
partition's leader election picks a new one, and the group's
coordination moves with it automatically, so a coordinator
failover is just a partition failover wearing a different name.
The client must handle the not-coordinator error: if it asks the
wrong broker, because its metadata is stale after a failover, the
broker tells it who the coordinator is now rather than
half-serving the request, because a coordinator request served
by a non-coordinator is a rebalance decided by a broker with no
authority to decide it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from relay.errors import Invalid


def coordinator_partition(group: str, offset_partitions: int) -> int:
    if offset_partitions < 1:
        raise Invalid("the offset store needs partitions")
    digest = hashlib.sha256(group.encode()).hexdigest()
    return int(digest[:8], 16) % offset_partitions


@dataclass
class CoordinatorLocator:
    offset_partitions: int
    partition_leaders: dict[int, str]

    def coordinator_for(self, group: str) -> str:
        partition = coordinator_partition(
            group, self.offset_partitions
        )
        leader = self.partition_leaders.get(partition)
        if leader is None:
            raise Invalid(
                f"the offset partition {partition} for group "
                f"{group} has no leader; coordination is "
                "unavailable until that partition elects one"
            )
        return leader

    def serve_or_redirect(
        self, group: str, asked_broker: str
    ) -> str:
        real = self.coordinator_for(group)
        if asked_broker == real:
            return f"{asked_broker} coordinates {group}"
        raise Invalid(
            f"NOT_COORDINATOR: {asked_broker} is not the "
            f"coordinator for {group}; it is {real}. A "
            "coordinator request served by a non-coordinator is "
            "a rebalance decided without authority"
        )

    def on_failover(
        self, partition: int, new_leader: str
    ) -> str:
        self.partition_leaders[partition] = new_leader
        return (
            f"offset partition {partition} failed over to "
            f"{new_leader}; every group it coordinates moved "
            "with it, a coordinator failover that is just a "
            "partition failover"
        )
