"""Partitioners: where an unkeyed record goes, and why sticky beats round-robin.

A keyed record's partition is fixed by its key hash, but an
unkeyed record can go anywhere, and the choice shapes batching.
Round-robin spreads unkeyed records evenly across partitions,
which sounds fair and batches terribly: with N partitions, a
producer's records are scattered one-per-partition, so each
partition's batch fills N times slower and the producer sends
many small batches instead of few large ones, paying per-batch
overhead N times over. The sticky partitioner is the
counterintuitive fix: it sends all unkeyed records to one
partition until that partition's batch is full or its linger
time expires, then switches to another. Over time the load is
still even, because each partition takes its turn as the sticky
target, but at any instant records concentrate into one fat
batch, so the producer sends fewer, larger batches and its
throughput rises. The model measures batches produced under each
strategy for the same record stream, because the sticky win is
invisible in a correctness test and obvious in a batch count, and
the whole point is a number the round-robin intuition gets wrong.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class RoundRobinPartitioner:
    partitions: int
    next_partition: int = 0

    def __post_init__(self) -> None:
        if self.partitions < 1:
            raise Invalid("need at least one partition")

    def assign(self) -> int:
        chosen = self.next_partition
        self.next_partition = (chosen + 1) % self.partitions
        return chosen


@dataclass
class StickyPartitioner:
    partitions: int
    batch_size: int
    current: int = 0
    in_batch: int = 0
    batches_produced: int = 1

    def __post_init__(self) -> None:
        if self.partitions < 1 or self.batch_size < 1:
            raise Invalid("partitions and batch size are positive")

    def assign(self) -> int:
        if self.in_batch >= self.batch_size:
            self.current = (self.current + 1) % self.partitions
            self.in_batch = 0
            self.batches_produced += 1
        self.in_batch += 1
        return self.current


def count_batches_roundrobin(
    records: int, partitions: int, batch_size: int
) -> int:
    per_partition = [0] * partitions
    partitioner = RoundRobinPartitioner(partitions)
    batches = 0
    for _ in range(records):
        p = partitioner.assign()
        per_partition[p] += 1
        if per_partition[p] % batch_size == 1:
            batches += 1
    return batches


def compare_strategies(
    records: int, partitions: int, batch_size: int
) -> str:
    rr = count_batches_roundrobin(records, partitions, batch_size)
    sticky = StickyPartitioner(partitions, batch_size)
    for _ in range(records):
        sticky.assign()
    return (
        f"{records} records, {partitions} partitions, batch "
        f"{batch_size}: round-robin sends {rr} batches, sticky "
        f"sends {sticky.batches_produced}; the sticky win is a "
        "number the round-robin intuition gets wrong"
    )
