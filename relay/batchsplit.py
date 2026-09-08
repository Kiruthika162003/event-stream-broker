"""Batch split: an over-large batch is halved and retried, down to one record.

A producer batches records to amortize the per-request cost, but a
batch can grow past the broker's maximum request size, especially
after compression turns out worse than the producer estimated, and
the broker rejects the whole batch as too large. Rather than fail
the records, the producer splits the rejected batch into smaller
batches and retries them, and the natural split is in half, because
halving repeatedly reaches a size that fits in a logarithmic number
of retries without needing to know the exact limit in advance. The
split preserves order: the first half's records keep their original
relative order ahead of the second half's, so splitting does not
reorder a keyed stream, which would break the per-key ordering the
producer promised. The recursion has a floor: a single record that
alone exceeds the maximum cannot be split further, and the producer
must fail that record rather than loop forever halving a batch of
one, because the record is simply too large for the cluster's
configured limit and no amount of splitting changes that. The
splitter refuses a maximum size below the largest single record up
front, surfacing the un-sendable record as a configuration problem
rather than discovering it after several pointless retries. The
report states how many batches the split produced, because a
producer that sent one batch and now sends eight has multiplied its
request count, a cost that argues for a smaller batch size or
better compression rather than repeated splitting at send time.
"""

from __future__ import annotations

from relay.errors import Invalid


def split_batch(record_sizes: list[int], max_size: int) -> list[list[int]]:
    if max_size < 1:
        raise Invalid("the maximum batch size must be positive")
    oversized = [s for s in record_sizes if s > max_size]
    if oversized:
        raise Invalid(
            f"record of size {max(oversized)} exceeds the maximum "
            f"{max_size} on its own; splitting cannot help, it must "
            "be failed as too large for the cluster's limit"
        )
    return _split(record_sizes, max_size)


def _split(records: list[int], max_size: int) -> list[list[int]]:
    if not records:
        return []
    if sum(records) <= max_size:
        return [records]
    if len(records) == 1:
        return [records]
    mid = len(records) // 2
    return _split(records[:mid], max_size) + _split(records[mid:], max_size)


def split_report(record_sizes: list[int], max_size: int) -> str:
    batches = split_batch(record_sizes, max_size)
    return (
        f"{len(record_sizes)} record(s) split into {len(batches)} "
        f"batch(es) under {max_size}; a large fan-out multiplies "
        "the request count and argues for a smaller batch size or "
        "better compression, not repeated splitting at send time"
    )
