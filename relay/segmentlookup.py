"""Segment lookup: which of many segments holds an offset, found by halving.

A partition's log is not one file but a sequence of segments, each
named by the base offset of its first record, and a read for an
offset must first find which segment holds it before the within-
segment index can find the byte position. Because the segments are
ordered by base offset and never overlap, the containing segment is
the one with the largest base offset not greater than the target,
which a binary search over the base offsets finds in logarithmic
time even for a partition with thousands of segments. The search
returns a floor, the same discipline the offset index uses one
level down: land on the segment whose base is at or below the
target and never above it, because a segment whose base is past the
target cannot contain it. A target below the first segment's base
is not in the log at all, it is in a segment already deleted by
retention, so the lookup refuses it rather than pointing at the
oldest surviving segment, which would silently start the read later
than asked. A target at or past the log end is likewise refused,
because no segment holds a record not yet written. The active
segment, the last one, has no successor bounding it, so a target in
its range resolves to it and the read runs to the log end. The
report states how many segments the search skipped, because a
partition whose reads always land in the active segment is being
tailed, while one whose reads scatter across old segments is
serving historical replays that keep old segments hot and
un-deletable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Missing


@dataclass
class SegmentSet:
    base_offsets: list[int] = field(default_factory=list)
    log_end: int = 0

    def log_start(self) -> int:
        return self.base_offsets[0] if self.base_offsets else 0

    def segment_for(self, target: int) -> int:
        if not self.base_offsets or target < self.base_offsets[0]:
            raise Missing(
                f"offset {target} is below the log start "
                f"{self.log_start()}; its segment was deleted by "
                "retention, it is not in the log"
            )
        if target >= self.log_end:
            raise Missing(
                f"offset {target} is at or past the log end "
                f"{self.log_end}; no segment holds an unwritten record"
            )
        low, high, found = 0, len(self.base_offsets) - 1, self.base_offsets[0]
        while low <= high:
            mid = (low + high) // 2
            if self.base_offsets[mid] <= target:
                found = self.base_offsets[mid]
                low = mid + 1
            else:
                high = mid - 1
        return found

    def is_active(self, base: int) -> bool:
        return bool(self.base_offsets) and base == self.base_offsets[-1]

    def read_locality(self, target: int) -> str:
        base = self.segment_for(target)
        idx = self.base_offsets.index(base)
        skipped = idx
        if self.is_active(base):
            return (
                f"offset {target} lands in the active segment "
                f"(base {base}); this partition is being tailed"
            )
        return (
            f"offset {target} lands in an old segment (base {base}, "
            f"{skipped} segment(s) before it); a historical replay "
            "keeps old segments hot and un-deletable"
        )
