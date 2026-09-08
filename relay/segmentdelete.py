"""Segment delete: rename now, unlink later, so an open read is not yanked.

When retention decides a segment is past its life the broker does
not unlink the file immediately, because a consumer may have opened
that segment for a read that is still in flight, and unlinking it
mid-read on some filesystems fails the read or serves garbage.
Instead the delete is two steps: the segment is renamed with a
deleted suffix at once, which removes it from the set of segments
new reads can open, and the file is unlinked only after a delay,
giving reads that already opened it time to finish. The rename is
the important half for correctness: the moment it happens no new
read can find the segment, so the population of reads that could
still touch it is fixed and can only shrink, and the delay just has
to outlast the longest of those already-open reads. The delay is a
bound, not a guarantee of zero open readers, so it is set longer
than any reasonable read takes, and the manager refuses to unlink
while a read that opened before the rename is still recorded as
active, because unlinking under a live reader is the exact hazard
the delay exists to avoid. It also refuses to rename a segment
twice, because a second delete of an already-renamed segment is a
bookkeeping error that could unlink a file a different segment now
occupies. The report states how long until the unlink and how many
readers opened before the rename, because a segment whose unlink
keeps deferring has a long-running read holding it, which is worth
knowing when disk is not being reclaimed as fast as retention
promised.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class SegmentDeletion:
    delay_ticks: int
    renamed_at: int = -1
    open_readers: int = 0
    finished: int = 0
    unlinked: bool = False

    def __post_init__(self) -> None:
        if self.delay_ticks < 1:
            raise Invalid("the delete delay must be positive")

    def rename(self, now: int, readers_open: int) -> str:
        if self.renamed_at >= 0:
            raise Invalid(
                "this segment is already renamed for deletion; a "
                "second delete could unlink a file another segment "
                "now occupies"
            )
        self.renamed_at = now
        self.open_readers = readers_open
        return (
            f"renamed at {now}; no new read can open it, "
            f"{readers_open} read(s) still in flight before the unlink"
        )

    def reader_finished(self) -> None:
        if self.finished < self.open_readers:
            self.finished += 1

    def try_unlink(self, now: int) -> str:
        if self.renamed_at < 0:
            raise Invalid("cannot unlink a segment that was never renamed")
        remaining = self.open_readers - self.finished
        if now - self.renamed_at < self.delay_ticks and remaining > 0:
            raise Invalid(
                f"{remaining} read(s) opened before the rename are "
                "still active and the delay has not elapsed; "
                "unlinking under a live reader is the hazard the "
                "delay exists to avoid"
            )
        self.unlinked = True
        return f"unlinked at {now}; disk reclaimed"

    def status(self, now: int) -> str:
        if self.renamed_at < 0:
            return "not yet marked for deletion"
        due = self.renamed_at + self.delay_ticks
        remaining = self.open_readers - self.finished
        return (
            f"unlink due at {due} ({max(0, due - now)} tick(s) away), "
            f"{remaining} pre-rename read(s) still holding it"
        )
