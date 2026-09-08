"""Ordering scope: order is a per-partition promise, not a topic-wide one.

The broker guarantees that records within one partition are
delivered in the order they were appended, and that is the entire
ordering promise: it says nothing about the order of records across
different partitions. Records land in a partition by their key, so
all records for one key go to one partition and are therefore
ordered relative to each other, which is why keying by an entity id
is how you get per-entity ordering, all of one customer's events in
sequence. But two records with different keys may be in different
partitions, and then their relative order is not defined: a
consumer reading multiple partitions can see them in either order,
because the partitions are consumed independently and interleaved
by whichever has data ready. This is the misunderstanding behind a
whole class of bugs, a system that assumed a record written after
another would be processed after it, when the two had different
keys and went to different partitions with no order between them.
The model maps keys to partitions and answers, for two records,
whether their order is guaranteed, which it is exactly when they
share a partition, and it refuses to claim a topic-wide ordering,
because the only way to order a whole topic is a single partition,
which serializes all throughput onto one broker and throws away the
parallelism partitions exist for. The report states how many
distinct partitions a set of keys spread across, because a
consumer needing order across those keys either must key them
together, accepting the single-partition bottleneck for that
group, or must order them itself after consuming, and knowing the
spread is what tells it which keys it cannot assume anything about.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class OrderingScope:
    partitions: int

    def __post_init__(self) -> None:
        if self.partitions < 1:
            raise Invalid("a topic needs at least one partition")

    def partition_for(self, key: str) -> int:
        return (hash(key) & 0x7FFFFFFF) % self.partitions

    def ordered_between(self, key_a: str, key_b: str) -> bool:
        return self.partition_for(key_a) == self.partition_for(key_b)

    def order_note(self, key_a: str, key_b: str) -> str:
        if self.ordered_between(key_a, key_b):
            return (
                f"'{key_a}' and '{key_b}' share a partition; their order "
                "is guaranteed"
            )
        return (
            f"'{key_a}' and '{key_b}' are on different partitions; no "
            "order between them, a consumer can see either first"
        )

    def spread(self, keys: list[str]) -> str:
        used = {self.partition_for(k) for k in keys}
        if self.partitions == 1:
            return (
                "one partition orders the whole topic but serializes all "
                "throughput onto one broker, the parallelism thrown away"
            )
        return (
            f"{len(keys)} key(s) spread across {len(used)} partition(s); "
            "order across them needs keying them together or ordering "
            "after consuming"
        )
