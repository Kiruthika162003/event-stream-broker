"""Hybrid logical clock: timestamps near wall time that still track causality.

A Lamport clock respects causality but its numbers drift far from
wall-clock time, so they are useless for a human reading a log or
for a query like give me records from the last minute. A plain wall
clock is readable but violates causality when clocks skew. A hybrid
logical clock gets both: a timestamp is a physical component, the
wall-clock reading, plus a small logical counter that breaks ties
and carries causality when the physical clock does not advance. On
a local event the HLC takes the max of its last timestamp and the
current physical time; if the physical time moved ahead it uses it
with the counter reset to zero, and if it did not, because two
events fell in the same clock tick or the clock went backward, it
keeps the physical component and bumps the counter, so the
timestamp still advances. On receiving a message it takes the max
across its own physical, the message's, and the current physical,
advancing the counter enough to stay ahead of both, which gives it
Lamport's guarantee that a receive is stamped after its send while
keeping the physical component close to real time. The closeness is
bounded: the counter only grows when the physical clock stalls, and
a well-behaved clock keeps it near zero, so the HLC stays within a
small bound of wall time, and a counter that climbs is a symptom of
a physical clock stuck or running backward, surfaced rather than
hidden. The clock ticks on a local event, updates on a receive, and
compares timestamps as physical-then-counter, and it reports the
counter, because a growing counter is the clock skew the hybrid
design is papering over, worth knowing before it grows past the
bound.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HybridLogicalClock:
    physical: int = 0
    counter: int = 0

    def tick(self, wall_now: int) -> tuple[int, int]:
        if wall_now > self.physical:
            self.physical = wall_now
            self.counter = 0
        else:
            # clock did not advance (same tick or went back): bump the counter
            self.counter += 1
        return (self.physical, self.counter)

    def on_receive(self, wall_now: int, msg: tuple[int, int]) -> tuple[int, int]:
        msg_physical, msg_counter = msg
        new_physical = max(self.physical, msg_physical, wall_now)
        if new_physical == self.physical == msg_physical:
            self.counter = max(self.counter, msg_counter) + 1
        elif new_physical == self.physical:
            self.counter += 1
        elif new_physical == msg_physical:
            self.counter = msg_counter + 1
        else:
            self.counter = 0
        self.physical = new_physical
        return (self.physical, self.counter)

    def drift_note(self, wall_now: int) -> str:
        if self.counter > 0 and self.physical >= wall_now:
            return (
                f"counter at {self.counter}; the physical clock stalled or "
                "went back and the counter is carrying causality, a skew the "
                "hybrid design papers over, worth watching before the bound"
            )
        return f"counter {self.counter}; physical component near wall time"

    @staticmethod
    def compare(a: tuple[int, int], b: tuple[int, int]) -> int:
        if a < b:
            return -1
        if a > b:
            return 1
        return 0
