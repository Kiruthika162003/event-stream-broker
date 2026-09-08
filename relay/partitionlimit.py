"""Partition limit: a cluster caps total partitions, not just per topic.

Choosing a topic's partition count is a per-topic decision, but
there is a second limit that spans the whole cluster: the total
number of partitions across every topic. It matters because several
costs scale with that total rather than with data volume. The
controller holds metadata for every partition, so a huge total
bloats the metadata it must store, propagate to brokers, and replay
on failover. Leadership failover is per-partition, so when a broker
dies the controller must elect a new leader for each of its
partitions, and a cluster with a million partitions fails over far
slower than one with ten thousand, turning a broker restart into a
long unavailability. Open file handles, replication connections,
and per-partition memory all scale with the total too. So the
cluster caps the total partition count, and a new topic whose
partitions would push the total over the cap is refused, not
because the data is too much but because the cluster's control
plane cannot manage that many partitions responsively. The limiter
tracks the current total against the cap, admits a topic creation
whose partitions fit, and refuses one that would exceed the cap,
naming that the limit is the control plane's, not the storage's,
because an operator seeing a topic-create rejected on a cluster with
plenty of disk needs to know the constraint is partition count, not
space. It refuses a cap or a topic partition count below one, and
reports the headroom, because a cluster near its partition cap is
one whose next failover will be slow, a warning to raise the cap
deliberately or consolidate topics before it bites."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class PartitionLimit:
    cap: int
    topics: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.cap < 1:
            raise Invalid("the partition cap must be positive")

    def total(self) -> int:
        return sum(self.topics.values())

    def create(self, topic: str, partitions: int) -> str:
        if partitions < 1:
            raise Invalid("a topic needs at least one partition")
        if topic in self.topics:
            raise Invalid(f"topic '{topic}' already exists")
        if self.total() + partitions > self.cap:
            raise Invalid(
                f"creating '{topic}' with {partitions} would push the total to "
                f"{self.total() + partitions}, over the cap {self.cap}; the "
                "limit is the control plane's, not the disk's, so failover "
                "stays fast"
            )
        self.topics[topic] = partitions
        return f"created '{topic}'; total {self.total()}/{self.cap}"

    def headroom(self) -> str:
        left = self.cap - self.total()
        return (
            f"{left} partition(s) of headroom; near the cap means the next "
            "failover will be slow, raise the cap deliberately or consolidate "
            "topics before it bites"
        )
