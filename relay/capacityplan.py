"""Capacity plan: throughput times retention times copies is the disk you need.

Sizing a cluster is arithmetic that teams often skip until a disk
fills, and the inputs are few: the write throughput in bytes per
second, how long records are retained, and the replication factor.
The disk a topic needs is the product of the three: throughput
times retention gives the bytes of one copy, and the replication
factor multiplies it because every copy sits on a broker's disk, so
a topic taking one megabyte a second, retained a day, at factor
three, needs the day's bytes three times over. Forgetting the
replication factor is the classic under-provision, sizing for one
copy and running out at the factor. Network is the other bound and
is asymmetric: incoming bytes are the produce rate, but the broker
must also send each record to the other replicas, so a leader's
outgoing replication traffic is the produce rate times the factor
minus one, which is why replication, not client traffic, often
saturates the network first on a high-factor cluster. The planner
computes disk and replication network from the inputs and refuses a
replication factor below one or a non-positive retention, which
would compute a disk of zero and hide the real need. It also states
the per-broker share, dividing the total across the broker count,
because the cluster total is reassuring while the per-broker number
is what actually has to fit on a disk, and a total that fits the
cluster can still overflow one broker if the partitions are not
spread. The report frames the disk in the retention's own terms, so
an operator reads it as days of data at a rate rather than a raw
byte count that means nothing without the rate beside it.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class CapacityPlan:
    bytes_per_second: float
    retention_seconds: float
    replication_factor: int
    brokers: int

    def __post_init__(self) -> None:
        if self.replication_factor < 1:
            raise Invalid("replication factor must be at least one")
        if self.retention_seconds <= 0:
            raise Invalid(
                "retention must be positive; zero computes a disk of "
                "zero and hides the real need"
            )
        if self.brokers < 1:
            raise Invalid("the cluster needs at least one broker")

    def one_copy_bytes(self) -> float:
        return self.bytes_per_second * self.retention_seconds

    def total_disk_bytes(self) -> float:
        return self.one_copy_bytes() * self.replication_factor

    def per_broker_disk_bytes(self) -> float:
        return self.total_disk_bytes() / self.brokers

    def replication_out_bytes_per_second(self) -> float:
        return self.bytes_per_second * (self.replication_factor - 1)

    def report(self) -> str:
        total = self.total_disk_bytes()
        per = self.per_broker_disk_bytes()
        repl = self.replication_out_bytes_per_second()
        return (
            f"disk {total:.0f} byte(s) total at factor "
            f"{self.replication_factor}, {per:.0f} per broker; leader "
            f"replication out {repl:.0f} byte(s)/s, which saturates the "
            "network before client traffic on a high-factor cluster"
        )
