"""Punctuate: a scheduled callback that fires on the clock you chose, not both.

A stream processor sometimes needs to do work on a schedule rather
than per record, emit a running aggregate every minute, expire idle
sessions, and it schedules that with a punctuation, a callback on an
interval. The interval can be measured against one of two clocks,
and the choice decides a behavior that surprises people. Stream-time
punctuation advances with the timestamps of the records flowing
through, so its interval is measured in event time and it fires only
as records arrive to push the stream time forward. This means a
stream that goes quiet stops punctuating on stream time entirely: no
records, no advance, no callback, so a session-expiry punctuation
that runs on stream time will not expire anything while the stream
is idle, exactly when expiry might matter. Wall-clock punctuation
advances with real time regardless of records, so it fires on
schedule even when the stream is silent, which is right for
liveness work and wrong for anything that must align with event
time, because wall-clock and event time drift apart when the stream
lags. The scheduler fires a stream-time punctuation only when the
observed stream time has advanced past the next scheduled mark, and
a wall-clock one whenever real time has, and it refuses a
non-positive interval, which would either never fire or fire
continuously. It reports, for a stream-time punctuation, how long
since it last fired in event time versus wall-clock, because a
growing gap between the two is the signature of a stalled stream
whose stream-time punctuations have silently stopped while the
operator expected them to keep running.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

STREAM_TIME = "stream-time"
WALL_CLOCK = "wall-clock"


@dataclass
class Punctuation:
    clock: str
    interval: int
    next_mark: int = 0
    fires: int = 0

    def __post_init__(self) -> None:
        if self.clock not in (STREAM_TIME, WALL_CLOCK):
            raise Invalid(f"unknown punctuation clock '{self.clock}'")
        if self.interval < 1:
            raise Invalid(
                "the interval must be positive; a zero interval never "
                "fires or fires continuously"
            )
        self.next_mark = self.interval

    def on_stream_time(self, stream_time: int) -> int:
        if self.clock != STREAM_TIME:
            return 0
        fired = 0
        while stream_time >= self.next_mark:
            self.next_mark += self.interval
            self.fires += 1
            fired += 1
        return fired

    def on_wall_clock(self, now: int) -> int:
        if self.clock != WALL_CLOCK:
            return 0
        fired = 0
        while now >= self.next_mark:
            self.next_mark += self.interval
            self.fires += 1
            fired += 1
        return fired

    def idle_note(self, stream_time: int, wall_clock: int) -> str:
        if self.clock != STREAM_TIME:
            return "wall-clock punctuation fires on schedule even when idle"
        gap = wall_clock - stream_time
        return (
            f"stream-time punctuation last mark {self.next_mark - self.interval}, "
            f"stream time {stream_time}, wall clock {wall_clock}: a "
            f"gap of {gap} means a stalled stream whose stream-time "
            "punctuations have silently stopped"
        )
