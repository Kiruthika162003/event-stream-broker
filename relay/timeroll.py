"""Time roll: seal a segment on age, so slow partitions still expire on time.

Segments roll on size, which works for busy partitions that fill
a segment in minutes, but starves a slow one: a partition
receiving a record an hour keeps one segment open for weeks,
because it never reaches the size threshold, and since retention
deletes whole sealed segments, that partition's oldest records
cannot be deleted until the segment finally seals, which by size
alone may be never. Time-based rolling fixes it by sealing a
segment once it has been open longer than a maximum, regardless
of size, so even a trickle partition produces a steady stream of
small sealed segments that retention can act on. The interaction
with retention is the point: without time roll, a topic with a
short retention window and a slow partition would keep records
far past their supposed expiry, because the records are trapped
in an unsealed segment that retention cannot touch, so retention
that looks tight on paper leaks on slow partitions specifically.
The roll decision takes the earlier of the two triggers, size or
age, because both are ceilings and whichever comes first should
fire, and the report distinguishes a size roll, a busy partition
behaving normally, from a time roll, a slow partition being
rescued from retention starvation, because a sudden rise in time
rolls means partitions slowed down, a workload change worth
noticing, not a problem but a signal.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class TimeRollPolicy:
    max_bytes: int
    max_open_ticks: int
    size_rolls: int = 0
    time_rolls: int = 0

    def __post_init__(self) -> None:
        if self.max_bytes < 1 or self.max_open_ticks < 1:
            raise Invalid(
                "size and age limits must both be positive"
            )

    def should_roll(
        self,
        segment_bytes: int,
        opened_at: int,
        now: int,
        has_records: bool,
    ) -> str:
        if not has_records:
            return "empty segment does not roll"
        by_size = segment_bytes >= self.max_bytes
        by_age = now - opened_at >= self.max_open_ticks
        if by_size:
            self.size_rolls += 1
            return (
                "roll by size: a busy partition behaving normally"
            )
        if by_age:
            self.time_rolls += 1
            return (
                "roll by age: a slow partition rescued from "
                "retention starvation, its old records now "
                "sealable"
            )
        return "no roll: within both size and age"

    def report(self) -> str:
        return (
            f"{self.size_rolls} size roll(s), {self.time_rolls} "
            "time roll(s); a rise in time rolls means partitions "
            "slowed down, a workload change worth noticing"
        )
