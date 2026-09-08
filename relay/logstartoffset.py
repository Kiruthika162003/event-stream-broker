"""Log start offset: the floor that rises as old records go, below it is gone.

A partition's log does not start at offset zero forever. Retention
deletes old segments, and an explicit delete-records call can drop a
prefix on demand, and after either the earliest surviving record sits
at some offset greater than zero. That offset is the log start offset,
and it is the floor of what the partition can still serve. A fetch for
an offset below it is asking for records that have been deleted, and
the honest answer is out-of-range, not an empty response or the
nearest surviving record, because silently returning something else
would let a consumer believe it read data that is actually gone. The
log start offset only ever moves forward: a request to move it
backward would claim to restore deleted records, which is impossible,
so it is refused. Moving it forward past the high watermark is refused
too, because that would delete records that are committed but not yet
consumed by everyone, and moving it past the log end is meaningless
since there is nothing there to keep. A consumer whose committed
offset falls below the log start after a deletion is in the same
out-of-range situation and must reset, to earliest to resume at the
new floor or to latest to skip the gap, the same auto-reset decision a
brand-new consumer faces. The tracker holds the log start, high
watermark, and log end, advances the start forward only, decides
whether an offset is fetchable, and reports the deleted count below
the start, because that number is data a consumer can never get back,
the part of the stream that aged out before it was read."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class LogStartOffset:
    log_start: int = 0
    high_watermark: int = 0
    log_end: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.log_start <= self.high_watermark <= self.log_end:
            raise Invalid(
                "the log must satisfy 0 <= start <= high watermark <= end"
            )

    def advance_start(self, new_start: int) -> int:
        if new_start < self.log_start:
            raise Invalid(
                f"cannot move the start back from {self.log_start} to "
                f"{new_start}; that would claim to restore deleted records"
            )
        if new_start > self.high_watermark:
            raise Invalid(
                f"start {new_start} would pass the high watermark "
                f"{self.high_watermark}; that would delete committed records "
                "not yet consumed by everyone"
            )
        deleted = new_start - self.log_start
        self.log_start = new_start
        return deleted

    def is_fetchable(self, offset: int) -> bool:
        return self.log_start <= offset <= self.log_end

    def check_fetch(self, offset: int) -> str:
        if offset < self.log_start:
            raise Invalid(
                f"offset {offset} is below the log start {self.log_start}; "
                "out-of-range, those records are deleted, the consumer must "
                "reset to earliest or latest"
            )
        if offset > self.log_end:
            raise Invalid(f"offset {offset} is past the log end {self.log_end}")
        return f"offset {offset} is fetchable"

    def deleted_below_start(self) -> int:
        return self.log_start

    def note(self) -> str:
        return (
            f"log start {self.log_start}, high watermark {self.high_watermark}, "
            f"end {self.log_end}; {self.deleted_below_start()} record(s) aged "
            "out below the start, data a consumer can never get back"
        )
