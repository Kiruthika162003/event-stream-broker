"""The segment log: an append-only file that knows when to stop growing.

A partition's history lives in segments, each owning a
contiguous offset range starting at its base. Only the last
segment accepts appends; when it crosses the roll threshold it
seals, immutable from that moment, and a fresh segment opens at
the next offset. Sealing is what makes everything else cheap:
retention deletes whole sealed segments instead of rewriting
files, replication ships them as immutable blobs, and a reader
holding a sealed segment never needs a lock. Reads address
offsets, not positions, and a read below the first retained
base fails as Lagging with the exact window stated, because
"you have fallen behind, the log now starts at 4200" is a
recoverable situation and a silent empty result is a data-loss
report filed by nobody.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid, Lagging, Missing, Sealed
from relay.records import Record

ROLL_AT_BYTES = 4096


@dataclass
class Segment:
    base_offset: int
    records: list[Record] = field(default_factory=list)
    sealed: bool = False

    def append(self, record: Record) -> int:
        if self.sealed:
            raise Sealed(
                f"segment at base {self.base_offset} is sealed; "
                "immutability is the product, not the obstacle"
            )
        self.records.append(record)
        return self.base_offset + len(self.records) - 1

    def size_bytes(self) -> int:
        return sum(
            record.size_bytes() for record in self.records
        )

    def next_offset(self) -> int:
        return self.base_offset + len(self.records)

    def holds(self, offset: int) -> bool:
        return self.base_offset <= offset < self.next_offset()

    def read(self, offset: int) -> Record:
        if not self.holds(offset):
            raise Missing(
                f"offset {offset} is not in this segment"
            )
        return self.records[offset - self.base_offset]


@dataclass
class SegmentLog:
    segments: list[Segment] = field(default_factory=list)
    rolls: int = 0

    def __post_init__(self) -> None:
        if not self.segments:
            self.segments.append(Segment(base_offset=0))

    def _active(self) -> Segment:
        return self.segments[-1]

    def append(self, record: Record) -> int:
        active = self._active()
        if (
            active.size_bytes() + record.size_bytes()
            > ROLL_AT_BYTES
            and active.records
        ):
            active.sealed = True
            self.rolls += 1
            active = Segment(base_offset=active.next_offset())
            self.segments.append(active)
        return active.append(record)

    def first_offset(self) -> int:
        return self.segments[0].base_offset

    def next_offset(self) -> int:
        return self._active().next_offset()

    def read(self, offset: int) -> Record:
        if offset < self.first_offset():
            raise Lagging(
                f"offset {offset} is below the retained "
                f"window; the log now starts at "
                f"{self.first_offset()}, and saying so beats a "
                "silent empty result"
            )
        if offset >= self.next_offset():
            raise Missing(
                f"offset {offset} has not been written; the "
                f"log ends at {self.next_offset() - 1}"
            )
        for segment in self.segments:
            if segment.holds(offset):
                return segment.read(offset)
        raise Invalid("the segment chain has a hole")

    def drop_sealed_before(self, offset: int) -> int:
        dropped = 0
        while (
            len(self.segments) > 1
            and self.segments[0].sealed
            and self.segments[0].next_offset() <= offset
        ):
            self.segments.pop(0)
            dropped += 1
        return dropped

    def shape(self) -> str:
        sealed = sum(
            1 for segment in self.segments if segment.sealed
        )
        return (
            f"{len(self.segments)} segment(s), {sealed} "
            f"sealed, offsets {self.first_offset()}.."
            f"{self.next_offset() - 1}, {self.rolls} roll(s)"
        )
