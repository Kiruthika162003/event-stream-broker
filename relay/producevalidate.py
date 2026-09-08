"""Produce validation: reject the malformed batch at the door, whole.

A produce request carries a batch, and the batch can be wrong in
ways the broker must catch before a single record lands, because
a half-written batch is the worst partial state in the system:
some records durable, some rejected, and the producer with no
clean answer about which. Validation is therefore all-or-nothing
at the batch boundary. The checks are ordered cheapest first so
a request fails on the free check before the broker spends effort
on the expensive one: the topic must exist, the producer must be
authorized, the batch must be non-empty, the compression codec
must be one the broker understands, and the batch's declared
record count must match the records actually present, because a
count mismatch means the batch was truncated in transit and
appending a truncated batch writes records the producer did not
send. Only when every check passes does the batch append, and
the rejection names the first failed check so the producer fixes
the real problem instead of guessing through a generic error.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

KNOWN_CODECS = ("none", "gzip", "snappy", "zstd", "lz4")


@dataclass(frozen=True)
class ProduceBatch:
    topic: str
    codec: str
    declared_count: int
    records: tuple[bytes, ...]


@dataclass
class ProduceValidator:
    known_topics: set[str]
    authorized: set[tuple[str, str]]

    def validate(
        self, principal: str, batch: ProduceBatch
    ) -> str:
        if batch.topic not in self.known_topics:
            raise Invalid(
                f"topic {batch.topic} does not exist; the "
                "cheapest check first, before any work"
            )
        if (principal, batch.topic) not in self.authorized:
            raise Invalid(
                f"{principal} is not authorized to produce to "
                f"{batch.topic}"
            )
        if not batch.records:
            raise Invalid(
                "an empty batch is not a produce request"
            )
        if batch.codec not in KNOWN_CODECS:
            raise Invalid(
                f"unknown codec {batch.codec}; the broker will "
                "not store bytes it cannot decompress"
            )
        if batch.declared_count != len(batch.records):
            raise Invalid(
                f"count mismatch: declared "
                f"{batch.declared_count}, carries "
                f"{len(batch.records)}; the batch was truncated "
                "in transit and appending it writes records the "
                "producer never sent"
            )
        return (
            f"batch of {len(batch.records)} record(s) accepted "
            f"for {batch.topic}, whole or not at all"
        )
