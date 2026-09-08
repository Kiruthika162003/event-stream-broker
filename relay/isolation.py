"""Isolation level: how far a consumer may read into uncommitted territory.

A consumer declares an isolation level, and it decides where the
consumer's readable horizon ends. Read-uncommitted reads up to
the high watermark, seeing every replicated record including
those inside transactions not yet committed, which is fast and
occasionally wrong: a record it processed may belong to a
transaction that later aborts, so the consumer acted on data that
un-happened. Read-committed reads only up to the last stable
offset, the offset before the earliest still-open transaction, so
it never sees a record whose transaction might still abort, at the
cost of blocking behind a long-running open transaction that
holds the stable offset back. The distinction is the last-stable-
offset versus the high-watermark, and a broker that served
read-committed consumers up to the high watermark would leak
uncommitted records, the exact bug read-committed exists to
prevent. The trade is explicit and stated: read-committed pays
latency for correctness, and a read-committed consumer stalled
behind a stuck transaction is experiencing the guarantee working,
not a bug, which is why the transaction timeout matters, it bounds
how long one open transaction can hold every read-committed
consumer back. The resolver names which offset bounds each level
and why, because a consumer surprised by either the latency or
the aborted record chose the wrong level without knowing the
trade.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

READ_UNCOMMITTED = "read-uncommitted"
READ_COMMITTED = "read-committed"
LEVELS = (READ_UNCOMMITTED, READ_COMMITTED)


@dataclass(frozen=True)
class PartitionOffsets:
    high_watermark: int
    last_stable_offset: int

    def __post_init__(self) -> None:
        if self.last_stable_offset > self.high_watermark:
            raise Invalid(
                "the last stable offset cannot exceed the high "
                "watermark; committed is a subset of replicated"
            )


def readable_ceiling(
    level: str, offsets: PartitionOffsets
) -> tuple[int, str]:
    if level not in LEVELS:
        raise Invalid(f"unknown isolation level {level}")
    if level == READ_UNCOMMITTED:
        return offsets.high_watermark, (
            "up to the high watermark; fast, but a record inside "
            "a transaction that later aborts is one the consumer "
            "acted on that un-happened"
        )
    return offsets.last_stable_offset, (
        "up to the last stable offset; never sees a record whose "
        "transaction might abort, at the cost of blocking behind "
        "a long-running open transaction"
    )


def uncommitted_gap(offsets: PartitionOffsets) -> str:
    gap = offsets.high_watermark - offsets.last_stable_offset
    if gap == 0:
        return "no open transactions; both levels read the same"
    return (
        f"{gap} record(s) are replicated but not stable; a "
        "read-committed consumer stalled here is the guarantee "
        "working, not a bug, which is why the transaction timeout "
        "bounds the stall"
    )
