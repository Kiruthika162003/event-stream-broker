"""Ring buffer: keep the last N of something, and let the rest fall off the back.

A broker keeps windows of recent things in memory, the last few
hundred request latencies for a percentile, the recent throughput
samples for a rate, and it wants a fixed bound on that memory
regardless of how long it runs. A ring buffer gives exactly that: a
fixed-capacity array with a write position that wraps, so appending
past capacity overwrites the oldest entry rather than growing, and
the buffer always holds at most its capacity, the most recent that
many. This is the right structure when only the recent window
matters and old data is meant to fall off, which is most of a
broker's in-memory metrics: keeping every latency forever would be
unbounded memory for a statistic that only cares about the recent
shape. The buffer appends in constant time and reads its contents
in order from oldest to newest, which is what a windowed statistic
needs, and it never blocks or rejects an append, because an
overwrite is the intended behavior, not an error, the difference
from a bounded queue that refuses when full. The buffer refuses a
zero or negative capacity, which could hold nothing, and it
distinguishes a buffer not yet full, where reads return only what
was written, from a wrapped one, where reads return the last
capacity entries in age order. It reports how full it is and
whether it has wrapped, because a statistic computed over a buffer
that has not yet filled is over fewer samples than the window
implies, and treating a half-full window as full understates the
variance a fuller window would show, a subtle bias worth surfacing
when the buffer is young.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class RingBuffer:
    capacity: int
    _data: list[int] = field(default_factory=list)
    _pos: int = 0
    _wrapped: bool = False

    def __post_init__(self) -> None:
        if self.capacity < 1:
            raise Invalid("a ring buffer needs positive capacity")

    def append(self, value: int) -> None:
        if len(self._data) < self.capacity:
            self._data.append(value)
        else:
            self._data[self._pos] = value
            self._wrapped = True
        self._pos = (self._pos + 1) % self.capacity

    def contents(self) -> list[int]:
        if not self._wrapped:
            return list(self._data)
        # oldest first: start at the write position and wrap
        return self._data[self._pos:] + self._data[: self._pos]

    def size(self) -> int:
        return len(self._data)

    def has_wrapped(self) -> bool:
        return self._wrapped

    def fill_note(self) -> str:
        if not self._wrapped:
            return (
                f"{self.size()}/{self.capacity} filled, not yet wrapped; a "
                "statistic over this is fewer samples than the window "
                "implies, understating variance"
            )
        return f"full at {self.capacity}, overwriting the oldest on each append"
