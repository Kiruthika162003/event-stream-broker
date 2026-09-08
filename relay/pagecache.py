"""Page cache: a consumer that stays near the end never touches the disk.

A broker does not cache records itself; it relies on the operating
system's page cache, and a read is fast or slow depending on
whether the bytes it wants are still in that cache. A consumer
reading near the log end reads bytes the producer wrote moments
ago, which are certainly still in cache because they were just
written, so its reads never touch the disk and cost almost nothing.
A consumer far behind reads old bytes long since evicted from
cache, so its reads fault to disk, and the damage is not confined
to the slow consumer: the disk reads it triggers pull old pages
into cache and evict the recent pages the healthy consumers were
reading cheaply, so one lagging consumer can turn every consumer's
reads from cache hits into disk faults. This is why lag is a
performance contagion, not a private problem of the lagging
consumer, and why keeping consumers caught up protects the whole
broker's read path. The model estimates whether a consumer's read
position falls inside the cached window, the most recent bytes the
cache can hold, and flags a read that falls outside it as a disk
fault that also evicts hot pages. The model refuses a cached-window
larger than the log, because a cache cannot hold more than exists,
and a window claimed larger than the data would hide real faults
behind an impossible assumption. The report states how far behind
the cache edge a consumer is, because the fix for a consumer just
past the edge is a slightly larger cache while the fix for one far
past it is more consumers or a faster one.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class CacheModel:
    log_start: int
    log_end: int
    cached_bytes: int
    bytes_per_offset: int

    def __post_init__(self) -> None:
        log_bytes = (self.log_end - self.log_start) * self.bytes_per_offset
        if self.cached_bytes > log_bytes:
            raise Invalid(
                "the cached window cannot exceed the log; a cache "
                "cannot hold more than exists, and claiming so hides "
                "real faults"
            )

    def cache_edge(self) -> int:
        cached_offsets = self.cached_bytes // self.bytes_per_offset
        return self.log_end - cached_offsets

    def is_cache_hit(self, read_offset: int) -> bool:
        return read_offset >= self.cache_edge()

    def classify(self, read_offset: int) -> str:
        edge = self.cache_edge()
        if read_offset >= edge:
            return (
                f"offset {read_offset} is inside the cached window "
                f"(edge {edge}); served from cache, no disk"
            )
        behind = edge - read_offset
        return (
            f"offset {read_offset} is {behind} offset(s) behind the "
            f"cache edge {edge}; a disk fault that also evicts hot "
            "pages, so this lag slows every consumer, not just this one"
        )
