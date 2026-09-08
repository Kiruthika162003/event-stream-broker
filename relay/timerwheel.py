"""Timer wheel: schedule and expire thousands of timeouts without a sorted list.

The broker holds many operations that each have a timeout, a
delayed produce waiting for replication, a fetch waiting for data,
a heartbeat waiting to lapse, and it needs to fire each when its
time comes without scanning them all every tick. A sorted list of
timeouts would cost a logarithmic insert and make the earliest easy
but the rest slow to manage; a timing wheel does better by bucketing
timeouts into slots by when they fire, so inserting is putting a
timeout in the slot for its expiry, a constant-time operation, and
advancing the clock is expiring one slot's worth at a time, also
constant per tick regardless of how many timeouts are pending. The
wheel has a fixed number of slots covering a span of time, and a
timeout is placed in the slot at its expiry offset from the current
position, wrapping around the wheel. A timeout further out than the
wheel's span does not fit in any slot, and a single-level wheel
handles that by refusing it, where a real broker chains a coarser
wheel above to hold the overflow; this implementation refuses the
overflow and names the span, so the caller sizes the wheel for its
longest timeout rather than silently losing a far-future one. The
wheel advances tick by tick, expiring the timeouts in each slot it
passes, and it refuses to advance backwards, since time moves one
way and a backward advance would re-expire slots already fired. It
refuses a timeout in the past, which should fire immediately rather
than wait a full wheel revolution to come around again, the bug a
naive modulo placement would cause. It reports how many timeouts
are pending across the wheel, because a wheel filling faster than it
drains is operations timing out slower than they arrive.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class TimerWheel:
    slots: int
    now: int = 0
    buckets: dict[int, list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.slots < 1:
            raise Invalid("a timer wheel needs at least one slot")

    def schedule(self, name: str, expiry: int) -> str:
        if expiry <= self.now:
            raise Invalid(
                f"expiry {expiry} is at or before now {self.now}; it should "
                "fire immediately, not wait a full revolution to come around"
            )
        if expiry - self.now > self.slots:
            raise Invalid(
                f"expiry {expiry} is beyond the wheel's span of {self.slots} "
                f"from now {self.now}; chain a coarser wheel or size this one "
                "for its longest timeout"
            )
        slot = expiry % self.slots
        self.buckets.setdefault(slot, []).append(name)
        return f"scheduled '{name}' in slot {slot} for expiry {expiry}"

    def advance(self, to: int) -> list[str]:
        if to < self.now:
            raise Invalid("time moves one way; a backward advance re-expires slots")
        fired = []
        for tick in range(self.now + 1, to + 1):
            slot = tick % self.slots
            fired.extend(self.buckets.pop(slot, []))
        self.now = to
        return fired

    def pending(self) -> str:
        total = sum(len(v) for v in self.buckets.values())
        return (
            f"{total} timeout(s) pending across the wheel; a wheel filling "
            "faster than it drains is operations timing out slower than they "
            "arrive"
        )
