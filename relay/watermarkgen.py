"""Watermark generation: the frontier of event time, trailing the max by a bound.

A stream processing on event time needs to know when it has seen
enough of a time range to act on it, close a window, fire a timer,
and the watermark is that signal: a watermark of time T asserts
that no record with an event time at or before T will arrive after
it, so anything waiting on times up to T can proceed. The generator
derives the watermark from the records it sees, and the derivation
must account for out-of-order arrival, because records do not
arrive in event-time order, a record for nine oh five can arrive
after one for nine ten. So the watermark is not the latest event
time seen but that latest minus an allowed-lateness bound, the
window within which out-of-order records are still expected, and
the bound is the promise: a record later than the watermark by more
than the bound is declared late and handled by the lateness policy
rather than delaying the watermark for it. The watermark only ever
advances, never retreats, because a window closed at a watermark
cannot un-close, so a record with an earlier event time than the
current max does not pull the watermark back. The catch is an idle
source: if no records arrive, the watermark stalls at its last
value, and downstream windows waiting on it never close even though
wall-clock time passes, so the generator advances the watermark on
an idleness timeout to keep a quiet source from freezing the
pipeline. It refuses a negative lateness bound, which would put the
watermark ahead of the events, and reports the gap between the max
event time and the watermark, because that gap is the lateness the
generator is tolerating and the delay it adds before a window can
close."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class WatermarkGenerator:
    lateness_bound: int
    max_event_time: int = 0
    watermark: int = 0
    _seen: bool = False

    def __post_init__(self) -> None:
        if self.lateness_bound < 0:
            raise Invalid(
                "a negative lateness bound puts the watermark ahead of the "
                "events"
            )

    def observe(self, event_time: int) -> int:
        if not self._seen:
            self.max_event_time = event_time
            self._seen = True
        else:
            self.max_event_time = max(self.max_event_time, event_time)
        candidate = self.max_event_time - self.lateness_bound
        # the watermark only advances
        self.watermark = max(self.watermark, candidate)
        return self.watermark

    def is_late(self, event_time: int) -> bool:
        return self._seen and event_time < self.watermark

    def advance_on_idle(self, wall_now: int) -> int:
        # a quiet source: push the watermark to wall time minus the bound so
        # downstream windows still close
        candidate = wall_now - self.lateness_bound
        self.watermark = max(self.watermark, candidate)
        return self.watermark

    def tolerance(self) -> str:
        gap = self.max_event_time - self.watermark
        return (
            f"watermark {self.watermark} trails the max event time by {gap}; "
            "that gap is the lateness tolerated and the delay before a window "
            "can close"
        )
