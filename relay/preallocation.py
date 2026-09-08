"""Preallocation: reserve the segment's space now, so no append fails midway.

A segment file grows as records append, and if the disk fills
between one append and the next, an append can fail partway,
leaving a torn record that recovery must detect and truncate.
Preallocation avoids the torn tail by reserving the segment's
full size on disk the moment it is created, so every append into
it writes into space already guaranteed, and the disk-full
failure happens at segment creation, cleanly, rather than mid-
append, messily. The tradeoff is that a preallocated segment
occupies its full size immediately even while mostly empty, so a
broker with many partitions preallocating large segments reserves
a lot of disk it is not yet using, which looks alarming on a
utilization graph that cannot tell reserved-but-empty from
actually-full. The planner sizes preallocation against that: too
small and segments roll too often, too large and reserved space
dwarfs used space, and the sweet spot depends on the partition's
write rate, a busy partition fills a large preallocation quickly
while a slow one leaves it mostly empty for a long time. The
planner also handles the final segment specially: when a segment
seals it is truncated to its actual used size, returning the
unused preallocated tail to the disk, so the reservation is a
temporary cost during the segment's active life, not a permanent
one. The report distinguishes reserved from used bytes, because
an operator seeing high disk usage needs to know how much is
preallocation that will be reclaimed on seal versus data that
will not.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class PreallocatedSegment:
    reserved: int
    used: int = 0
    sealed: bool = False

    def __post_init__(self) -> None:
        if self.reserved < 1:
            raise Invalid("must reserve a positive size")

    def append(self, size: int) -> str:
        if self.sealed:
            raise Invalid("a sealed segment does not append")
        if self.used + size > self.reserved:
            raise Invalid(
                "append exceeds the reservation; roll to a new "
                "segment, the disk-full failure happens cleanly "
                "at creation not mid-append"
            )
        self.used += size
        return f"appended into reserved space, {self.used}/{self.reserved}"

    def seal(self) -> str:
        reclaimed = self.reserved - self.used
        self.reserved = self.used
        self.sealed = True
        return (
            f"sealed and truncated, {reclaimed} reserved byte(s) "
            "returned to the disk; the reservation was temporary"
        )


@dataclass
class PreallocationReport:
    segments: list[PreallocatedSegment] = field(
        default_factory=list
    )

    def totals(self) -> str:
        reserved = sum(s.reserved for s in self.segments)
        used = sum(s.used for s in self.segments)
        slack = reserved - used
        return (
            f"{reserved} reserved, {used} used, {slack} "
            "preallocated slack reclaimed on seal; an operator "
            "seeing high usage needs reserved-but-empty told apart "
            "from data that stays"
        )
