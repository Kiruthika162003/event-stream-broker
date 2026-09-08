"""Segment roll: the active segment closes on the first limit it hits.

The active segment does not grow forever; it rolls, closing and
starting a new one, on whichever of several limits it reaches
first. Size is the obvious one: a segment past its byte limit
rolls. Time is the second: a segment older than the roll interval
rolls even if it is nearly empty, so a low-traffic partition still
produces segments that retention can eventually delete rather than
one endless segment that never ages out. The third is the index
filling: the offset index has a fixed size, and a segment holding
so many small records that its index fills must roll even if the
segment's bytes are under the size limit, because there is nowhere
to record the next index entry. The roll decision is the minimum
across these, the first trigger to fire, and which one fires tells
an operator something: rolling on time means the partition is slow,
rolling on size means it is busy, and rolling on the index means
its records are unusually small, each a different characterization
of the workload. The planner takes the current size, age, and index
fill against their limits and reports which limit will trigger the
roll and when, so an operator sizing segments sees whether the
partition rolls on size as intended or is rolling early on time or
the index, which changes segment count and therefore open file
handles and retention granularity. It refuses a zero or negative
limit, which would roll continuously, and reports the trigger, so a
partition producing far more segments than expected is diagnosed as
one rolling on a limit other than the one the operator sized for.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class RollPlan:
    size_limit: int
    time_limit: int
    index_limit: int

    def __post_init__(self) -> None:
        if min(self.size_limit, self.time_limit, self.index_limit) < 1:
            raise Invalid("every roll limit must be positive")

    def should_roll(self, size: int, age: int, index_entries: int) -> bool:
        return (
            size >= self.size_limit
            or age >= self.time_limit
            or index_entries >= self.index_limit
        )

    def trigger(self, size: int, age: int, index_entries: int) -> str:
        reached = []
        if size >= self.size_limit:
            reached.append(("size", "the partition is busy"))
        if age >= self.time_limit:
            reached.append(("time", "the partition is slow"))
        if index_entries >= self.index_limit:
            reached.append(("index", "its records are unusually small"))
        if not reached:
            return "no roll yet; the segment is under every limit"
        names = ", ".join(f"{n} ({why})" for n, why in reached)
        return f"rolling on {names}"

    def remaining(self, size: int, age: int, index_entries: int) -> str:
        # keep (name, remaining) pairs in priority order so a tie resolves
        # deterministically to size, then time, then index; keying a dict by
        # the remaining values would collide when two are equal and silently
        # pick whichever was assigned last, an order-of-insertion bug
        candidates = [
            ("size", self.size_limit - size),
            ("time", self.time_limit - age),
            ("index", self.index_limit - index_entries),
        ]
        which, soonest = min(candidates, key=lambda c: c[1])
        return (
            f"rolls next on {which} in {max(0, soonest)}; a partition rolling "
            "on a limit other than the one it was sized for changes the "
            "segment count and open file handles"
        )
