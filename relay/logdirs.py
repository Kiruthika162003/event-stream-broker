"""Log directories: many disks per broker, balanced, and one can fail alone.

A broker often has several disks, and it spreads partitions across
them rather than striping, because a partition living entirely on
one disk means a disk failure loses only the partitions on that
disk, not a fraction of every partition, which is the difference
between losing some replicas the cluster can re-replicate and
corrupting all of them at once. The placer balances partitions
across disks by count and by size, because a disk that holds the
few largest partitions fills first even with a fair count, so
balance must weigh bytes, not just number. The failure model is
the point of the whole design: when a disk fails, the broker
takes only the partitions on that disk offline, staying alive to
serve the partitions on its healthy disks, and it reports the
failed disk's partitions as needing re-replication from their
other replicas rather than crashing the whole broker. This is why
a disk per partition beats striping a partition across disks: the
blast radius of a disk failure is one disk's partitions, a
bounded and re-replicable loss, instead of every partition
damaged. The rebalancer moves partitions off a filling disk to a
emptier one, but only new or fully-replicated partitions, because
moving a partition that is the sole surviving replica risks it in
transit, so the mover refuses to relocate a partition that cannot
afford the move, naming it rather than risking it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class LogDirBalancer:
    disks: list[str]
    partition_disk: dict[int, str] = field(default_factory=dict)
    partition_size: dict[int, int] = field(default_factory=dict)
    offline_disks: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not self.disks:
            raise Invalid("a broker needs at least one disk")

    def place(self, partition: int, size: int) -> str:
        healthy = [d for d in self.disks if d not in self.offline_disks]
        if not healthy:
            raise Invalid("no healthy disk to place on")
        bytes_on: dict[str, int] = dict.fromkeys(healthy, 0)
        for p, disk in self.partition_disk.items():
            if disk in bytes_on:
                bytes_on[disk] += self.partition_size.get(p, 0)
        chosen = min(healthy, key=lambda d: (bytes_on[d], d))
        self.partition_disk[partition] = chosen
        self.partition_size[partition] = size
        return f"partition {partition} placed on {chosen}"

    def fail_disk(self, disk: str) -> str:
        if disk not in self.disks:
            raise Invalid(f"{disk} is not a disk of this broker")
        self.offline_disks.add(disk)
        stranded = sorted(
            p
            for p, d in self.partition_disk.items()
            if d == disk
        )
        return (
            f"{disk} failed: {stranded} offline and need "
            "re-replication from other replicas; the broker stays "
            "alive for its healthy disks, a bounded blast radius"
        )

    def relocate(
        self, partition: int, sole_replica: bool
    ) -> str:
        if partition not in self.partition_disk:
            raise Invalid(f"partition {partition} is not placed")
        if sole_replica:
            raise Invalid(
                f"partition {partition} is the sole surviving "
                "replica; moving it risks it in transit, named "
                "rather than risked"
            )
        self.place(partition, self.partition_size[partition])
        return f"partition {partition} relocated to balance bytes"
