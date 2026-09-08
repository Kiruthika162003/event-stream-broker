"""FindCoordinator: a group's coordinator is wherever its offsets partition lives.

Before a consumer can join a group it must find the group's
coordinator, the broker that owns the group's membership and
committed offsets, and the design avoids a lookup service by
deriving the coordinator from the group id itself. The group id is
hashed to a partition of the internal offsets topic, and the
leader of that partition is the coordinator, so every broker can
compute the same answer from the group id and the cluster metadata
without asking anyone, and the coordinator moves only when that
partition's leadership moves. This ties two things together
deliberately: a group's coordinator and a group's committed
offsets live on the same broker, so committing an offset and
updating membership are local operations, not cross-broker ones.
The hash must be stable, because a group that hashed to a
different partition after an upgrade would find a coordinator with
none of its state, so the mapping is a fixed function of the group
id and the offsets topic partition count, and changing that count
would remap every group, which is why the offsets topic partition
count is effectively frozen once a cluster has groups. The resolver
refuses to answer while the target partition has no leader,
because a coordinator lookup during that partition's own election
has no valid answer and must be retried, not answered with a stale
broker. The report states which partition a group mapped to,
because two groups complaining about the same slow coordinator are
usually two groups hashed to the same overloaded partition.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class CoordinatorMap:
    offsets_partitions: int
    leaders: dict[int, str | None]

    def __post_init__(self) -> None:
        if self.offsets_partitions < 1:
            raise Invalid("the offsets topic needs a partition")

    def partition_for(self, group_id: str) -> int:
        return (hash(group_id) & 0x7FFFFFFF) % self.offsets_partitions

    def coordinator_for(self, group_id: str) -> str:
        part = self.partition_for(group_id)
        leader = self.leaders.get(part)
        if leader is None:
            raise Invalid(
                f"offsets partition {part} for group '{group_id}' "
                "has no leader right now; the lookup must be "
                "retried, not answered with a stale broker"
            )
        return leader

    def colocated(self, group_a: str, group_b: str) -> bool:
        return self.partition_for(group_a) == self.partition_for(group_b)
