"""Offset index: a sparse map from offset to file position, searched by halving.

A fetch names a starting offset, and the broker must turn that
logical offset into a physical byte position in the segment file
so it can seek there and start reading, and scanning the whole
segment from the front to find it would make every fetch cost the
whole log. The offset index avoids the scan by keeping, for a
sparse subset of records, a pair of offset and file position, so a
fetch binary-searches the index for the largest indexed offset not
past the target, seeks to its position, and scans forward only the
short distance from there to the target. Sparse is the deliberate
choice: indexing every record would make the index as large as the
log, so it indexes roughly one record per index-interval bytes,
trading a bounded forward scan for an index small enough to keep in
memory. The search returns a floor, the largest indexed offset at
or below the target, because the target itself is usually not
indexed and the reader must land at or before it and scan the
rest, never after it, since landing after would skip records. The
index refuses an offset below its base, which belongs to an
already-deleted segment, and an empty index returns the segment
start, because a segment with no indexed entries yet is scanned
from the front, which is cheap while it is short. The report
states the average scan distance the sparsity implies, because an
index interval too large turns every fetch into a long forward
scan the index was supposed to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid, Missing


@dataclass
class OffsetIndex:
    base_offset: int
    interval_bytes: int = 4096
    entries: list[tuple[int, int]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.interval_bytes < 1:
            raise Invalid("index interval must be positive")

    def add(self, offset: int, position: int) -> None:
        if offset < self.base_offset:
            raise Invalid(
                f"offset {offset} is below the segment base "
                f"{self.base_offset}; it belongs to a deleted "
                "segment, not this one"
            )
        if self.entries and offset <= self.entries[-1][0]:
            raise Invalid(
                "index entries must be strictly increasing; a "
                "record cannot index behind the last one"
            )
        self.entries.append((offset, position))

    def floor_position(self, target: int) -> int:
        if target < self.base_offset:
            raise Missing(
                f"offset {target} predates this segment's base "
                f"{self.base_offset}; look in an earlier segment"
            )
        low, high, found = 0, len(self.entries) - 1, 0
        while low <= high:
            mid = (low + high) // 2
            if self.entries[mid][0] <= target:
                found = self.entries[mid][1]
                low = mid + 1
            else:
                high = mid - 1
        return found

    def average_scan(self, record_bytes: int) -> str:
        if record_bytes < 1:
            raise Invalid("record size must be positive")
        records_per_entry = max(1, self.interval_bytes // record_bytes)
        return (
            f"an index entry every {self.interval_bytes} byte(s) "
            f"means a fetch scans forward ~{records_per_entry} "
            "record(s) on average; too wide an interval turns the "
            "fetch into the long scan the index was to prevent"
        )
