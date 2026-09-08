"""Write amplification: how many bytes hit disk for each byte a client sent.

A client that produces a megabyte does not cause a megabyte of disk
writes, it causes several, and the ratio of bytes actually written
to bytes the client produced is the write amplification, a number
that explains why a broker's disk IO can far exceed its client
throughput. The bytes come from several sources. The produce append
writes the client's bytes once to the leader's log. Replication
writes them again on each follower, so a replication factor of
three writes the record three times across the cluster. Compaction
rewrites live records into new segments as it reclaims space, so a
heavily-compacted topic writes its data more than once over its
life. The index and time-index writes add a little per record. The
sum over the client bytes is the amplification, and it decomposes
the disk IO into what the durability and compaction machinery costs
versus the raw data. The decomposition is what makes it actionable:
an amplification dominated by replication is the price of the
chosen factor, not tunable without changing durability, while one
dominated by compaction is a topic compacting too aggressively,
tunable by relaxing the compaction trigger. The calculator sums the
components against the client bytes and reports the ratio and its
largest contributor. It refuses zero client bytes, which makes the
ratio undefined, and a negative component. It names the dominant
source, because an operator seeing disk IO far above client
throughput needs to know whether it is the replication factor they
chose, the compaction they configured, or a genuine data increase,
three different responses to the same symptom."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class WriteAmplification:
    client_bytes: int
    replication_factor: int
    compaction_rewrites: int
    index_bytes: int

    def __post_init__(self) -> None:
        if self.client_bytes < 1:
            raise Invalid("client bytes must be positive; the ratio is undefined at zero")
        if self.replication_factor < 1 or self.compaction_rewrites < 0 or self.index_bytes < 0:
            raise Invalid("factor at least one, rewrites and index non-negative")

    def replication_bytes(self) -> int:
        return self.client_bytes * self.replication_factor

    def compaction_bytes(self) -> int:
        return self.client_bytes * self.compaction_rewrites

    def total_written(self) -> int:
        return self.replication_bytes() + self.compaction_bytes() + self.index_bytes

    def ratio(self) -> float:
        return self.total_written() / self.client_bytes

    def dominant(self) -> str:
        parts = {
            "replication": self.replication_bytes(),
            "compaction": self.compaction_bytes(),
            "index": self.index_bytes,
        }
        return max(parts, key=parts.get)

    def report(self) -> str:
        top = self.dominant()
        hint = {
            "replication": "the factor you chose, not tunable without durability",
            "compaction": "compacting too aggressively, relax the trigger",
            "index": "index overhead, usually small",
        }[top]
        return (
            f"{self.ratio():.1f}x write amplification, dominated by {top}: "
            f"{hint}; disk IO far above client throughput is one of these three"
        )
