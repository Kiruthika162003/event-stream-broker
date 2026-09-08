"""Timestamp skew: a producer's fast clock poisons retention and windows.

A record carries a timestamp, and when it is the producer's event
time the broker trusts a value it did not generate, which is fine
until the producer's clock is wrong. A producer whose clock runs
ahead stamps records with timestamps in the broker's future, and
two mechanisms that depend on timestamps break. Time-based
retention deletes records older than the retention period, measured
from the record's timestamp, so a record stamped far in the future
is never old enough to delete and lingers forever, and enough of
them defeat retention on the partition. Time-based windowing places
a record in the window its timestamp falls in, so a future-stamped
record lands in a window that has not happened yet and either
inflates a future window or is dropped as impossibly late,
depending on the watermark. The broker guards against this by
bounding how far ahead of its own clock a record's timestamp may
be: a record within the allowed skew is accepted as-is, trusting
the producer's clock within tolerance, and one beyond the skew is
rejected, because a timestamp that far off is a broken clock, not a
real event time, and accepting it corrupts retention and windowing
downstream. The guard checks the record timestamp against the
broker's clock plus the max skew, rejects one too far ahead naming
the skew, and it deliberately does not bound how far behind a
timestamp may be, because an old timestamp is a legitimate late or
replayed record that retention and windowing already handle,
whereas a future one is always an error. It reports the skew of an
accepted record so a producer drifting toward the limit is visible
before its records start being rejected, the warning that a clock
is slipping before it slips past the bound.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class SkewGuard:
    max_skew: int

    def __post_init__(self) -> None:
        if self.max_skew < 0:
            raise Invalid("the max skew cannot be negative")

    def check(self, record_ts: int, broker_now: int) -> str:
        skew = record_ts - broker_now
        if skew > self.max_skew:
            raise Invalid(
                f"record timestamp is {skew} ahead of the broker, past the "
                f"max skew {self.max_skew}; a broken clock not an event time, "
                "accepting it corrupts retention and windowing"
            )
        return f"accepted; {skew} ahead of the broker, within the skew"

    def is_future_poison(self, record_ts: int, broker_now: int) -> bool:
        return record_ts - broker_now > self.max_skew

    def drift_note(self, record_ts: int, broker_now: int) -> str:
        skew = record_ts - broker_now
        if skew <= 0:
            return "record is at or behind the broker clock; a normal past event"
        headroom = self.max_skew - skew
        return (
            f"{skew} ahead, {headroom} before the skew bound; a producer "
            "drifting toward it is a clock slipping before records are rejected"
        )
