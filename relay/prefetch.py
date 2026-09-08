"""Prefetch: read ahead so processing never waits, but not so far it drowns.

A consumer that fetches a batch, processes it, then fetches the
next, spends half its time waiting on the network with the
processor idle. Prefetch overlaps them: while the processor works
on batch one, the consumer fetches batch two, so the next batch is
already in memory when the processor asks for it and processing
never blocks on the network. The danger is prefetching too far
ahead: a consumer that fetches faster than it processes
accumulates unprocessed batches in memory until it runs out, the
same unbounded-buffer failure the producer side has, arriving
from the other direction. The prefetcher bounds the read-ahead to
a small number of batches, enough to hide network latency, few
enough to bound memory, and it pauses fetching when the buffer is
full, resuming when processing drains it below a low mark. The
resume threshold is deliberately below the pause threshold, a
hysteresis band, because resuming the instant the buffer drops
one batch below full makes the consumer fetch a single batch,
fill up, pause, and repeat, thrashing between paused and fetching
every batch, and a low-water mark distinct from the high-water
mark lets the consumer fetch a useful run before pausing again.
The report states buffer occupancy and whether prefetch is
currently paused, because a consumer permanently paused is one
whose processing cannot keep up with even the bounded read-ahead,
a signal that the bottleneck is the processor, not the network,
which is the opposite of what prefetch was tuned to fix.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class Prefetcher:
    high_mark: int
    low_mark: int
    buffered: int = 0
    paused: bool = False

    def __post_init__(self) -> None:
        if self.low_mark >= self.high_mark:
            raise Invalid(
                "the low mark must be below the high mark, or the "
                "consumer thrashes between paused and fetching "
                "every batch"
            )
        if self.low_mark < 0:
            raise Invalid("marks are nonnegative")

    def fetched(self, batches: int) -> str:
        self.buffered += batches
        if self.buffered >= self.high_mark:
            self.paused = True
            return (
                f"buffer at {self.buffered}, prefetch paused; "
                "read-ahead bounded so memory does not drown"
            )
        return f"buffer at {self.buffered}, prefetch continues"

    def processed(self, batches: int) -> str:
        self.buffered = max(0, self.buffered - batches)
        if self.paused and self.buffered <= self.low_mark:
            self.paused = False
            return (
                f"buffer drained to {self.buffered}, prefetch "
                "resumed; the hysteresis band lets a useful run "
                "fetch before pausing again"
            )
        return f"buffer at {self.buffered}"

    def report(self) -> str:
        state = "paused" if self.paused else "active"
        note = (
            "; permanently paused means the processor, not the "
            "network, is the bottleneck, the opposite of what "
            "prefetch fixes"
            if self.paused
            else ""
        )
        return (
            f"buffer {self.buffered}/{self.high_mark}, prefetch "
            f"{state}{note}"
        )
