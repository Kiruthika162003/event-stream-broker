"""The offset index: find a record without walking the log to it.

A segment holds thousands of records, and a consumer that
seeks to offset 8_412 should not read 8_411 records to get
there. The index is a sparse map from offset to byte position,
one entry every N records, so a lookup binary-searches the
sparse entries to the nearest indexed offset at or below the
target, then scans forward a bounded number of records. Sparse
is the deliberate choice: a dense index would rival the log in
size and double every write's cost, while a sparse index adds a
bounded scan in exchange for a fraction of the memory, and the
interval is the knob between seek latency and index size that
the report makes visible rather than magic. The index is
rebuildable from the log by construction, never the source of
truth, because an index that can disagree with the log is a
second truth, and the first rule of this broker is that the log
is the only truth.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field

from relay.errors import Invalid, Missing


@dataclass
class OffsetIndex:
    base_offset: int
    interval: int
    entries: list[tuple[int, int]] = field(default_factory=list)
    records_seen: int = 0

    def __post_init__(self) -> None:
        if self.interval < 1:
            raise Invalid("the index interval must be positive")

    def on_append(self, offset: int, position: int) -> None:
        if self.records_seen % self.interval == 0:
            self.entries.append((offset, position))
        self.records_seen += 1

    def seek(self, target: int) -> tuple[int, int]:
        if not self.entries:
            raise Missing("the index is empty")
        if target < self.entries[0][0]:
            raise Missing(
                f"offset {target} is below the first indexed "
                f"offset {self.entries[0][0]}"
            )
        offsets = [entry[0] for entry in self.entries]
        slot = bisect.bisect_right(offsets, target) - 1
        indexed_offset, position = self.entries[slot]
        scan = target - indexed_offset
        return position, scan

    def scan_bound(self) -> int:
        return self.interval - 1

    def report(self) -> str:
        density = (
            self.records_seen / len(self.entries)
            if self.entries
            else 0
        )
        return (
            f"{len(self.entries)} index entrie(s) for "
            f"{self.records_seen} record(s) "
            f"(1 per {density:.0f}), worst-case scan "
            f"{self.scan_bound()} record(s); the interval is "
            "the knob between seek latency and index size"
        )

    def rebuild_from(
        self, records: list[tuple[int, int]]
    ) -> None:
        self.entries = []
        self.records_seen = 0
        for offset, position in records:
            self.on_append(offset, position)
