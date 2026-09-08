"""Monotonic append time: the log's clock never goes backward, even if the OS does.

When a topic uses log-append time, the broker stamps each record
with its own clock, and the one property those stamps must have is
monotonicity: a record at a higher offset must not have a lower
timestamp than one before it, because the time index and every
time-based seek assume timestamps rise with offsets, and a
backward step breaks the binary search silently, returning wrong
offsets for time queries. The problem is that the OS clock is not
monotonic: NTP adjustments, leap seconds, and manual corrections
can step it backward, so a naive broker stamping records with the
raw wall clock can write a record whose timestamp is earlier than
its predecessor's, corrupting the ordering the index depends on.
The stamper enforces monotonicity by clamping: each record's
timestamp is the maximum of the current clock and the previous
record's timestamp, so a backward clock step produces a run of
equal timestamps rather than a decreasing one, which the index
tolerates because equal is not backward. This trades a small
inaccuracy, a few records stamped slightly late during a backward
step, for the invariant the index requires, and that trade is
correct because a timestamp off by the clock-step is a minor
imprecision while a non-monotonic log is a broken index. The
stamper counts the clamps, because a high clamp rate means the
broker's clock is stepping often, an NTP or hardware problem worth
fixing at the source rather than papering over forever with the
clamp.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class MonotonicStamper:
    last_stamp: int = 0
    clamps: int = 0
    stamped: int = 0

    def stamp(self, wall_clock: int) -> int:
        if wall_clock < 0:
            raise Invalid("the wall clock cannot be negative")
        self.stamped += 1
        if wall_clock < self.last_stamp:
            self.clamps += 1
            stamp = self.last_stamp
        else:
            stamp = wall_clock
        self.last_stamp = stamp
        return stamp

    def clamp_rate(self) -> str:
        if self.stamped == 0:
            raise Invalid("nothing stamped yet")
        pct = 100 * self.clamps / self.stamped
        note = (
            "; a high rate means the clock steps often, an NTP or "
            "hardware problem to fix at the source, not paper over"
            if pct > 5
            else ""
        )
        return (
            f"{self.clamps} clamp(s) in {self.stamped} stamp(s) "
            f"({pct:.0f}%){note}"
        )
