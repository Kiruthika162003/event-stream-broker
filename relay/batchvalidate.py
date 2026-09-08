"""Batch validation: the broker checks the batch it is about to trust forever.

A produced batch is about to become part of the log, immutable and
replicated, so the broker validates it at the door, because a bad
batch admitted is a bad batch every consumer and replica inherits.
The checks are ordered cheapest-first so a batch fails on the
quickest test it fails. The magic byte identifies the batch
format, and a wrong one means the client and broker disagree about
the wire format, so it is rejected before any field is parsed
against the wrong layout. The CRC covers the batch bytes, and a
mismatch means corruption in transit, network or memory, so the
batch is rejected before it corrupts the log, which is the whole
reason the CRC exists: corruption caught at the door has one
suspect, the wire, while corruption found later has the whole
cluster as suspects. The base-offset and last-offset-delta must
be consistent, so the batch's claimed record count matches its
span, because a batch that lies about its own size desyncs every
offset after it. The record count must be positive, because an
empty batch is a produce that produced nothing and is a client
bug worth surfacing, not silently accepting. The validator reports
which check failed, because a rejected produce needs a specific
cause, wrong-format sends the client to its serializer, CRC
mismatch sends it to its network, and offset inconsistency sends
it to its batching, three different fixes a generic invalid-batch
error cannot distinguish.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

SUPPORTED_MAGIC = 2


@dataclass(frozen=True)
class Batch:
    magic: int
    crc: int
    computed_crc: int
    base_offset: int
    last_offset_delta: int
    record_count: int


def validate_batch(batch: Batch) -> str:
    if batch.magic != SUPPORTED_MAGIC:
        raise Invalid(
            f"magic byte {batch.magic} is not the supported "
            f"{SUPPORTED_MAGIC}; the client and broker disagree on "
            "wire format, fix the serializer"
        )
    if batch.crc != batch.computed_crc:
        raise Invalid(
            f"CRC mismatch ({batch.crc} vs {batch.computed_crc}): "
            "corruption in transit, caught at the door with one "
            "suspect, the wire, before it corrupts the log"
        )
    if batch.record_count < 1:
        raise Invalid(
            "an empty batch produced nothing; a client bug worth "
            "surfacing, not silently accepting"
        )
    if batch.last_offset_delta != batch.record_count - 1:
        raise Invalid(
            f"offset inconsistency: last-offset-delta "
            f"{batch.last_offset_delta} does not match "
            f"{batch.record_count} records; a batch that lies "
            "about its size desyncs every offset after it, fix "
            "the batching"
        )
    return (
        f"batch of {batch.record_count} record(s) valid at base "
        f"{batch.base_offset}"
    )
