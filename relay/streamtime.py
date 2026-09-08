"""Stream time: windows close on event time, and lateness is a decision.

Aggregating a stream into windows, counts per minute, sums per
hour, forces the hardest question in streaming: when is a window
done. Processing time is easy and wrong, because a record for
10:00 can arrive at 10:05 after a network delay, and a window
closed on the clock would miss it. Event time is right and hard,
because the stream must decide how long to wait for stragglers.
The watermark is the mechanism: it is the event time the stream
believes it has seen everything before, advanced as records
arrive, and a window closes when the watermark passes its end.
Records arriving after their window closed are late, and
lateness is a policy, not an error: within an allowed-lateness
grace the window reopens and updates, past it the record is
dropped to a side output and counted, because silently dropping
late data makes the aggregate quietly wrong while counting it
makes the lateness a number someone can act on. The watermark
only advances, because a retreating watermark would reopen
windows the stream already emitted as final, and downstream
consumers built on those emissions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class WindowedStream:
    window_size: int
    allowed_lateness: int
    watermark: int = 0
    windows: dict[int, int] = field(default_factory=dict)
    closed: set[int] = field(default_factory=set)
    dropped_late: int = 0

    def __post_init__(self) -> None:
        if self.window_size < 1 or self.allowed_lateness < 0:
            raise Invalid(
                "window size must be positive and lateness "
                "nonnegative"
            )

    def _window_start(self, event_time: int) -> int:
        return (event_time // self.window_size) * self.window_size

    def advance_watermark(self, to_time: int) -> list[int]:
        if to_time < self.watermark:
            raise Invalid(
                f"the watermark only advances: {to_time} is "
                f"behind {self.watermark}, and reopening emitted "
                "windows breaks every downstream that trusted "
                "the emission"
            )
        self.watermark = to_time
        newly_closed = []
        for start in sorted(self.windows):
            window_end = start + self.window_size
            if (
                start not in self.closed
                and self.watermark
                >= window_end + self.allowed_lateness
            ):
                self.closed.add(start)
                newly_closed.append(start)
        return newly_closed

    def add(self, event_time: int, value: int) -> str:
        start = self._window_start(event_time)
        window_end = start + self.window_size
        if start in self.closed:
            self.dropped_late += 1
            return (
                f"dropped: event at {event_time} is past its "
                f"closed window and the grace; counted as late, "
                "not swallowed"
            )
        if self.watermark >= window_end:
            self.windows[start] = self.windows.get(start, 0) + value
            return (
                f"late but in grace: event at {event_time} "
                f"reopened window [{start},{window_end})"
            )
        self.windows[start] = self.windows.get(start, 0) + value
        return f"on time: added to window [{start},{window_end})"

    def result(self, start: int) -> int:
        if start not in self.windows:
            raise Invalid(f"no window at {start}")
        return self.windows[start]

    def lateness_report(self) -> str:
        return (
            f"{len(self.closed)} window(s) closed, "
            f"{self.dropped_late} event(s) dropped past grace; "
            "a number someone can act on, not a silent wrong "
            "aggregate"
        )
