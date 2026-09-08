"""Batch header: one base offset, and every record's offset is a delta from it.

A record batch stores a single base offset in its header and gives
each contained record an offset delta rather than a full offset,
so a batch of a thousand records carries one absolute offset and a
thousand small deltas instead of a thousand absolute offsets, which
is why the deltas are varints small enough to cost a byte each. The
absolute offset of a record is the base offset plus its delta, and
the last offset delta in the header names the highest, so the
batch's last offset is base plus last-delta, and the next batch's
base offset is one past that. This layout has a consequence that
surprises people reading a compacted or transactional log: the
deltas are dense and contiguous within a batch even when the
absolute offsets in the partition are not contiguous across
batches, because control records and the base offsets of
transaction markers consume offsets between batches. The header
also carries the base timestamp and a max timestamp, so a record's
timestamp is likewise a delta from the base, keeping timestamps
compact for a batch produced in a tight window. The assembler
refuses a delta beyond the last-offset-delta the header declared,
because a record claiming an offset past the batch's stated end is
either corruption or a reader miscounting, and refuses a base
offset below the previous batch's end, because offsets across a
partition only ever increase. The report states the offset range a
batch covers, because a consumer that fetched a batch and got fewer
distinct offsets than records learns the batch spans a range with
gaps it did not expect.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class BatchHeader:
    base_offset: int
    last_offset_delta: int
    base_timestamp: int
    record_count: int

    def __post_init__(self) -> None:
        if self.last_offset_delta < 0:
            raise Invalid("the last offset delta cannot be negative")
        if self.record_count < 1:
            raise Invalid("a batch holds at least one record")

    def last_offset(self) -> int:
        return self.base_offset + self.last_offset_delta

    def next_base_offset(self) -> int:
        return self.last_offset() + 1

    def offset_of(self, delta: int) -> int:
        if not 0 <= delta <= self.last_offset_delta:
            raise Invalid(
                f"delta {delta} is outside the batch's range "
                f"0..{self.last_offset_delta}; a record past the "
                "stated end is corruption or a miscount"
            )
        return self.base_offset + delta

    def follows(self, previous: BatchHeader) -> bool:
        return self.base_offset == previous.next_base_offset()

    def coverage(self) -> str:
        span = self.last_offset_delta + 1
        gaps = span - self.record_count
        note = (
            f"offsets {self.base_offset}..{self.last_offset()} "
            f"({span} slot(s)) for {self.record_count} record(s)"
        )
        if gaps > 0:
            return (
                f"{note}; {gaps} offset slot(s) consumed by control "
                "records or markers, so the batch spans gaps"
            )
        return f"{note}; dense, no gaps"
