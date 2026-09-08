"""Leaky bucket: hold a burst and release it at a steady rate, or spill it.

The token bucket elsewhere in this package lets a saved-up burst
through all at once and only then limits to the refill rate; the
leaky bucket takes the opposite stance and is the right tool when
the thing being protected needs a smooth input, not an occasional
flood. Requests pour into a bucket with a fixed capacity, and the
bucket drains at a constant rate, so the output is always steady no
matter how bursty the input, and a burst that arrives faster than
the drain fills the bucket rather than passing straight through.
When the bucket is full, further requests spill, rejected, because
there is no room to hold them and admitting them would break the
steady output the bucket exists to produce. This is the difference
that matters: a token bucket smooths the average but passes bursts,
a leaky bucket smooths the output itself and never emits faster than
its drain, which suits a downstream that melts under a spike even a
brief one. The two knobs mean: the drain rate is the steady output,
and the capacity is how large a burst the bucket absorbs before
spilling, so a larger capacity tolerates a bigger burst at the cost
of more delay for the requests waiting in it. The bucket adds
arrivals up to capacity, drains by elapsed time times the rate, and
spills what does not fit, and it reports the spill count, because a
bucket that spills is a source producing faster than the protected
side can take sustainably, the signal to slow the source rather
than enlarge the bucket, which only delays the spill. It refuses a
non-positive capacity or drain rate, which could hold nothing or
never drain, and a backward clock, since draining needs monotonic
time.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class LeakyBucket:
    capacity: float
    drain_per_tick: float
    level: float = 0.0
    last_tick: int = 0
    spilled: int = 0

    def __post_init__(self) -> None:
        if self.capacity <= 0 or self.drain_per_tick <= 0:
            raise Invalid("capacity and drain rate must be positive")

    def _drain(self, now: int) -> None:
        if now < self.last_tick:
            raise Invalid("time went backwards; draining needs a monotonic clock")
        elapsed = now - self.last_tick
        self.level = max(0.0, self.level - elapsed * self.drain_per_tick)
        self.last_tick = now

    def offer(self, now: int, amount: float) -> str:
        self._drain(now)
        room = self.capacity - self.level
        if amount <= room:
            self.level += amount
            return f"admitted {amount}; level {self.level:.1f}/{self.capacity}"
        overflow = amount - room
        self.level = self.capacity
        self.spilled += 1
        return (
            f"spilled {overflow:.1f} of {amount}; the bucket is full and the "
            "source is producing faster than the drain sustains, slow the "
            "source rather than enlarge the bucket"
        )
