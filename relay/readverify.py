"""Read verify: check the checksum on the way out too, because disks rot.

A batch's CRC is checked when it arrives, but that is not the last
time corruption can strike: bits stored correctly can flip later, a
disk sector degrading, a cosmic ray, a firmware bug, so a batch that
passed its write-time check can be corrupt by the time it is read
back. Read-time verification catches that: when serving a fetch, the
broker recomputes the stored batch's CRC and compares it to the CRC
in the batch header, and a mismatch means the batch rotted on disk
since it was written. The broker must not serve the corrupt batch,
because handing corrupted data to a consumer as if it were the
producer's is worse than an error, so a failed verification refuses
the read of that batch. Refusing is not the end, though: the same
batch exists on the in-sync replicas, which stored their own copies
independently, so the broker can repair the corrupt local copy from
a replica that verifies, and then serve. This is why replication
protects against disk corruption and not only broker failure: a
replica is a second independent copy that a local rot did not
touch. Verifying every read costs CPU, so it is a tradeoff against
the corruption rate, and a broker that never verifies reads trusts
its disks completely, fine until a silent corruption is served and
believed. The verifier recomputes and compares, serves on a match,
refuses on a mismatch and marks the batch for repair, and it refuses
to repair from a replica whose own copy also fails to verify, since
copying corruption over corruption fixes nothing. It reports the
verification failure rate, because a rising rate is a disk starting
to fail, caught by read verification before the failure is total."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.crc32c import crc32c
from relay.errors import Invalid


@dataclass
class ReadVerifier:
    verify_failures: int = 0
    reads: int = 0

    def serve(self, data: bytes, stored_crc: int) -> str:
        self.reads += 1
        if crc32c(data) != stored_crc:
            self.verify_failures += 1
            raise Invalid(
                "read verification failed: the batch rotted on disk since it "
                "was written; refusing to serve corruption as the producer's "
                "data, repair it from an in-sync replica"
            )
        return "batch verified on read; served"

    def repair_from(self, replica_data: bytes, stored_crc: int) -> bytes:
        if crc32c(replica_data) != stored_crc:
            raise Invalid(
                "the replica's copy also fails to verify; copying corruption "
                "over corruption fixes nothing, try another replica"
            )
        return replica_data

    def failure_rate(self) -> str:
        if self.reads == 0:
            return "no reads verified yet"
        pct = self.verify_failures / self.reads * 100
        return (
            f"{self.verify_failures}/{self.reads} reads failed verification "
            f"({pct:.1f}%); a rising rate is a disk starting to fail, caught "
            "before the failure is total"
        )
