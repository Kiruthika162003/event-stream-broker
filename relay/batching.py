"""Batching and compression: amortize the overhead, but measure the ratio.

Every record carries per-record overhead, a header, a length, a
checksum, and sending records one at a time pays that overhead
on every one. A batch pays it once for many records, which is
why throughput systems batch, and the batch is also the unit of
compression: a compressor sees the shared structure across
records in a batch and shrinks it, where compressing one record
alone often grows it because the compression header exceeds the
savings. The accounting the broker keeps is honest about the
second fact: compression is applied per batch and the resulting
size is compared to the raw size, and a batch that compressed
larger than it started, which happens for already-compressed
payloads like images, is stored uncompressed with the attempt
recorded, because storing a negative saving to honor a config
flag is paying to make data bigger. The report states the
realized ratio across batches, not the advertised one, because
the compressor's brochure and the payload's reality disagree
on every binary topic.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

PER_RECORD_OVERHEAD = 30
BATCH_OVERHEAD = 60


@dataclass
class Batch:
    raw_record_bytes: list[int]

    def __post_init__(self) -> None:
        if not self.raw_record_bytes:
            raise Invalid("an empty batch is not a batch")

    def unbatched_bytes(self) -> int:
        return sum(
            size + PER_RECORD_OVERHEAD
            for size in self.raw_record_bytes
        )

    def batched_bytes(self) -> int:
        return sum(self.raw_record_bytes) + BATCH_OVERHEAD

    def overhead_saved(self) -> int:
        return self.unbatched_bytes() - self.batched_bytes()


@dataclass
class CompressionLedger:
    compressor: str
    batches_stored: int = 0
    stored_compressed: int = 0
    stored_raw_negative: int = 0
    total_raw: int = 0
    total_stored: int = 0

    def store(self, batch: Batch, compressed_size: int) -> str:
        if compressed_size < 0:
            raise Invalid("a compressed size cannot be negative")
        raw = batch.batched_bytes()
        self.batches_stored += 1
        self.total_raw += raw
        if compressed_size < raw:
            self.stored_compressed += 1
            self.total_stored += compressed_size
            return (
                f"compressed {raw} -> {compressed_size} bytes "
                f"with {self.compressor}"
            )
        self.stored_raw_negative += 1
        self.total_stored += raw
        return (
            f"stored raw: {self.compressor} grew {raw} to "
            f"{compressed_size}, and paying to make data bigger "
            "honors no config worth honoring"
        )

    def realized_ratio(self) -> str:
        if self.total_raw == 0:
            raise Invalid("nothing stored to measure")
        ratio = self.total_raw / self.total_stored
        return (
            f"{self.batches_stored} batch(es): realized "
            f"{ratio:.2f}x, {self.stored_raw_negative} stored "
            "raw because compression grew them; the brochure "
            "and the payload disagree on every binary topic"
        )
