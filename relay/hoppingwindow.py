"""Hopping window: windows overlap, so one record lands in several at once.

A hopping window has a size and a hop, and the hop is smaller than
the size, so consecutive windows overlap: a size of ten with a hop
of five starts a new window every five while each spans ten, so at
any moment two windows are open and a record falls into both. This
is the difference from a tumbling window, where the hop equals the
size and windows do not overlap, each record in exactly one. The
overlap is the point: hopping windows give a smoothed, sliding view
of an aggregate, a count over the last ten updated every five,
rather than the sharp boundaries of tumbling windows where a
result jumps when a window closes. The cost of the overlap is
multiplicity: a record belongs to size-over-hop windows at once, so
a smaller hop for a smoother view means each record is counted into
more windows, more state and more output, and the ratio is exactly
how much extra work the smoothing costs. The model computes, for a
record at a time, every window it belongs to, the windows whose
start is at a hop multiple and whose span covers the time, and it
refuses a hop larger than the size, because that would leave gaps
between windows where a record falls into no window at all and is
silently dropped from every aggregate, the opposite of the overlap
a hopping window is for. It refuses a non-positive hop or size. The
report states the overlap factor, size over hop rounded up, because
that number is how many windows each record multiplies into and the
memory a hop chosen for smoothness will cost.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class HoppingWindows:
    size: int
    hop: int

    def __post_init__(self) -> None:
        if self.size < 1 or self.hop < 1:
            raise Invalid("size and hop must be positive")
        if self.hop > self.size:
            raise Invalid(
                "a hop larger than the size leaves gaps where a record "
                "falls into no window and is dropped from every "
                "aggregate, the opposite of a hopping window"
            )

    def windows_for(self, time: int) -> list[int]:
        earliest_start = ((time - self.size) // self.hop + 1) * self.hop
        earliest_start = max(0, earliest_start)
        starts = []
        start = earliest_start
        while start <= time:
            if start <= time < start + self.size:
                starts.append(start)
            start += self.hop
        return starts

    def overlap_factor(self) -> int:
        return -(-self.size // self.hop)

    def report(self) -> str:
        factor = self.overlap_factor()
        return (
            f"size {self.size} hop {self.hop}: each record lands in "
            f"{factor} window(s) at once; a smaller hop smooths the view "
            "and multiplies the state and output by that factor"
        )
