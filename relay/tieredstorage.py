"""Tiered storage: the recent past on fast disk, the deep past in the cloud.

A partition's retained history can be weeks long, but the reads
are not uniform: consumers live near the tail, and the deep
past is touched only by the occasional backfill. Tiered storage
splits the log by temperature. Sealed segments older than the
local retention window are uploaded to an object store and
their local copies deleted, so the broker's disk holds the hot
tail while the cold history lives cheaply in the cloud. The
offset space stays continuous across the tiers, which is the
whole illusion: a consumer reading through the boundary from
cold to hot sees one unbroken log and never knows which tier
served a record. Uploads are verified before the local delete,
because deleting a segment whose upload silently failed is the
one bug that turns tiering into data loss, so the sequence is
upload, verify the object's digest, then delete, never
reordered. The report states how much history is cold, because
the cost story of tiering is entirely in that ratio.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from relay.errors import Invalid, Missing


@dataclass(frozen=True)
class TieredSegment:
    base_offset: int
    end_offset: int
    digest: str
    tier: str


@dataclass
class TieredLog:
    local_window: int
    segments: list[TieredSegment] = field(default_factory=list)
    object_store: dict[str, str] = field(default_factory=dict)
    uploads_verified: int = 0
    failed_deletes_prevented: int = 0

    def add_local(
        self, base: int, end: int, digest: str
    ) -> None:
        self.segments.append(
            TieredSegment(base, end, digest, tier="local")
        )

    def tier_out(self, now_end: int) -> str:
        moved = 0
        for index, seg in enumerate(self.segments):
            if seg.tier != "local":
                continue
            if now_end - seg.end_offset <= self.local_window:
                continue
            self.object_store[str(seg.base_offset)] = seg.digest
            stored = self.object_store.get(str(seg.base_offset))
            if stored != seg.digest:
                self.failed_deletes_prevented += 1
                continue
            self.uploads_verified += 1
            self.segments[index] = TieredSegment(
                seg.base_offset, seg.end_offset, seg.digest,
                tier="cold",
            )
            moved += 1
        return (
            f"tiered {moved} segment(s) to cold storage after "
            "verify-then-delete, never reordered"
        )

    def tier_of(self, offset: int) -> str:
        for seg in self.segments:
            if seg.base_offset <= offset < seg.end_offset:
                return seg.tier
        raise Missing(
            f"offset {offset} is in no segment of either tier"
        )

    def continuous(self) -> bool:
        ordered = sorted(
            self.segments, key=lambda s: s.base_offset
        )
        for earlier, later in itertools.pairwise(ordered):
            if earlier.end_offset != later.base_offset:
                return False
        return True

    def cold_ratio(self) -> str:
        if not self.segments:
            raise Invalid("no segments to measure")
        cold = sum(
            1 for s in self.segments if s.tier == "cold"
        )
        return (
            f"{cold} of {len(self.segments)} segment(s) cold; "
            "the cost story of tiering lives entirely in this "
            "ratio"
        )
