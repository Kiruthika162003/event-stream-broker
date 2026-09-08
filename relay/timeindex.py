"""The time index: seek to a timestamp without the log recording clocks.

Consumers sometimes want to start from a time, replay everything
since 9am, not an offset, and the broker must answer without
having stamped records with wall-clock time, which it refuses to
do because clocks disagree across producers. The reconciliation
is a separate time index, built at append from the broker's own
receive time, mapping the first offset at or after each time
bucket. A timestamp seek binary-searches this sparse index to
the earliest offset whose append time is at or after the target,
so the answer is defined even when no record has exactly that
time. The index records broker receive time, not producer event
time, and the report says so plainly, because a consumer that
believes it seeked by event time when it seeked by ingest time
will be off by the producer-to-broker delay, and a difference a
consumer knows about is a caveat while one it does not is a bug.
A seek before the first indexed time returns the log start, a
seek after the last returns the log end, because a time query
outside the retained window has exactly two honest answers and
an error is not one of them.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class TimeIndex:
    interval: int
    entries: list[tuple[int, int]] = field(default_factory=list)
    records_seen: int = 0
    log_start: int = 0
    log_end: int = 0

    def __post_init__(self) -> None:
        if self.interval < 1:
            raise Invalid("the time index interval must be positive")

    def on_append(
        self, receive_time: int, offset: int
    ) -> None:
        if self.records_seen == 0:
            self.log_start = offset
        if self.records_seen % self.interval == 0 and (
            not self.entries
            or self.entries[-1][0] < receive_time
        ):
            self.entries.append((receive_time, offset))
        self.records_seen += 1
        self.log_end = offset + 1

    def offset_for_time(self, target_time: int) -> tuple[int, str]:
        if not self.entries:
            raise Invalid("the time index is empty")
        if target_time <= self.entries[0][0]:
            return self.log_start, (
                "seek before the first indexed time; returning "
                "the log start"
            )
        if target_time > self.entries[-1][0]:
            return self.log_end, (
                "seek after the last indexed time; returning the "
                "log end"
            )
        times = [entry[0] for entry in self.entries]
        slot = bisect.bisect_left(times, target_time)
        offset = self.entries[slot][1]
        return offset, (
            f"nearest ingest time at or after {target_time} is "
            f"offset {offset}; this is broker receive time, not "
            "producer event time, off by the ingest delay"
        )
