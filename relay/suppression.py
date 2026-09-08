"""Suppress: hold a window's updates and emit once, when it can no longer change.

A windowed aggregation emits a new result every time a record
updates the window, so a one-minute count that receives a hundred
records emits a hundred intermediate results, each superseded by
the next. For a downstream that wants only the final count per
window, those intermediates are noise and load. Suppression holds
the updates and emits only once per window, after the window has
closed and its grace period for late records has passed, so the one
result that leaves is the final one and no downstream ever sees a
value that later changed. The tradeoff is latency for correctness
of the single emission: a suppressed result cannot be emitted until
the window is certain to be final, so a consumer gets the answer
later than an unsuppressed stream would, but gets it once and
correct rather than many times and provisional. The buffer holds at
most one pending result per window, the latest, since earlier ones
are superseded, and it releases a window's result when the stream
time advances past the window end plus the grace period. The
suppressor refuses to emit a window still within its grace period,
because a late record could still change it and emitting now would
send a value that a later correction contradicts, defeating the
whole point of suppressing. It also bounds the buffer: if too many
windows are open at once, holding them all would grow memory
without limit, so it reports the open-window count against a bound
rather than silently accumulating. The report states how many
emissions suppression saved, the intermediates it absorbed, because
that number is the load taken off the downstream, the reason to
suppress in the first place.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class Suppressor:
    grace: int
    pending: dict[int, int] = field(default_factory=dict)
    absorbed: int = 0
    emitted: int = 0

    def __post_init__(self) -> None:
        if self.grace < 0:
            raise Invalid("the grace period cannot be negative")

    def update(self, window_end: int, value: int) -> None:
        if window_end in self.pending:
            self.absorbed += 1
        self.pending[window_end] = value

    def advance(self, stream_time: int) -> list[tuple[int, int]]:
        ready = [
            (end, val)
            for end, val in self.pending.items()
            if stream_time >= end + self.grace
        ]
        for end, _ in ready:
            del self.pending[end]
            self.emitted += 1
        return sorted(ready)

    def force_emit(self, window_end: int, stream_time: int) -> int:
        if stream_time < window_end + self.grace:
            raise Invalid(
                f"window {window_end} is still within its grace period "
                f"(until {window_end + self.grace}); a late record could "
                "still change it, and emitting now sends a value a "
                "later correction contradicts"
            )
        value = self.pending.pop(window_end)
        self.emitted += 1
        return value

    def savings(self) -> str:
        return (
            f"{self.absorbed} intermediate update(s) absorbed, "
            f"{self.emitted} final result(s) emitted; the absorbed "
            "count is the load taken off the downstream"
        )
