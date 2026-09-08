"""Partition count planning: the one number you cannot easily change later.

Choosing a topic's partition count is the decision that haunts,
because a keyed topic cannot be repartitioned without breaking
per-key order, so the number chosen at creation is effectively
permanent. The planner derives it from the two constraints that
actually bind. The first is throughput: a single partition has a
ceiling, set by one leader's disk and network, so the count must
be at least the target throughput divided by per-partition
capacity. The second is consumer parallelism: a consumer group
can have at most one consumer per partition actively reading, so
a group that needs sixteen consumers of parallelism needs at
least sixteen partitions, and a topic with four partitions caps
its group at four consumers no matter how many it starts. The
planner takes the maximum of the two, because both are floors and
the binding one is whichever is larger, then applies a modest
growth headroom, because the cost of a few extra partitions is
small and the cost of being one short is a migration. It also
names the ceiling: too many partitions is not free, each adds
metadata, open files, and rebalance cost, so a topic with ten
thousand partitions for a throughput that needs ten is a
different mistake in the other direction, and the planner flags
a count that exceeds the need by more than an order of magnitude.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class PartitionRequirements:
    target_throughput: int
    per_partition_capacity: int
    consumer_parallelism: int

    def __post_init__(self) -> None:
        if self.per_partition_capacity < 1:
            raise Invalid("per-partition capacity must be positive")
        if self.target_throughput < 1 or self.consumer_parallelism < 1:
            raise Invalid("throughput and parallelism are positive")


def plan_partitions(req: PartitionRequirements) -> int:
    by_throughput = -(
        -req.target_throughput // req.per_partition_capacity
    )
    floor = max(by_throughput, req.consumer_parallelism)
    return floor + max(1, floor // 4)


def explain_plan(req: PartitionRequirements) -> str:
    by_throughput = -(
        -req.target_throughput // req.per_partition_capacity
    )
    floor = max(by_throughput, req.consumer_parallelism)
    binding = (
        "throughput"
        if by_throughput >= req.consumer_parallelism
        else "consumer parallelism"
    )
    chosen = plan_partitions(req)
    return (
        f"{chosen} partition(s): floor {floor} bound by "
        f"{binding} (throughput needs {by_throughput}, "
        f"parallelism needs {req.consumer_parallelism}), plus "
        "headroom because being one short is a migration"
    )


def audit_count(req: PartitionRequirements, chosen: int) -> str:
    need = max(
        -(-req.target_throughput // req.per_partition_capacity),
        req.consumer_parallelism,
    )
    if chosen < need:
        raise Invalid(
            f"{chosen} partitions is below the need of {need}; "
            "a keyed topic cannot be repartitioned, so this is "
            "permanent under-provisioning"
        )
    if chosen > need * 10:
        return (
            f"{chosen} partitions vastly exceeds the need of "
            f"{need}; each adds metadata, open files, and "
            "rebalance cost, the mistake in the other direction"
        )
    return f"{chosen} partitions is well matched to a need of {need}"
