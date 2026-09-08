"""Quotas: one loud client throttled, not disconnected, and told why.

A shared broker without quotas is a broker owned by whoever
produces fastest, and the temptation is to answer the flood
with a disconnect, which turns a throughput problem into an
availability incident. The quota throttles instead: each client
has a byte-per-tick budget tracked over a sliding window, and a
client over budget is not refused, its next request is delayed
by exactly the time needed to bring its rate back under the
limit, so the client stays connected and self-corrects while
the broker stays fair. The delay is computed and returned, not
hidden, because a client that knows it was throttled for 40
ticks can back off, while a client that just sees latency
retries harder and makes it worse. The window is the honesty:
a burst is forgiven if the average holds, so a client that
sends a big batch and then waits is not punished for the shape
of its traffic, only for its sustained rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class ClientQuota:
    client_id: str
    bytes_per_tick: int
    window_ticks: int
    events: list[tuple[int, int]] = field(default_factory=list)
    throttle_ticks_applied: int = 0

    def __post_init__(self) -> None:
        if self.bytes_per_tick < 1 or self.window_ticks < 1:
            raise Invalid(
                "a quota needs a positive rate and window"
            )

    def _prune(self, now: int) -> None:
        cutoff = now - self.window_ticks
        self.events = [
            (tick, size)
            for tick, size in self.events
            if tick > cutoff
        ]

    def _windowed_bytes(self) -> int:
        return sum(size for _, size in self.events)

    def record(self, now: int, size: int) -> str:
        self._prune(now)
        self.events.append((now, size))
        allowed = self.bytes_per_tick * self.window_ticks
        used = self._windowed_bytes()
        if used <= allowed:
            return (
                f"{self.client_id}: {used} of {allowed} bytes "
                "in window, no throttle"
            )
        over = used - allowed
        delay = -(-over // self.bytes_per_tick)
        self.throttle_ticks_applied += delay
        return (
            f"{self.client_id}: {over} bytes over, delayed "
            f"{delay} tick(s) to restore the rate; connected "
            "and self-correcting, not disconnected"
        )

    def bill(self) -> str:
        return (
            f"{self.client_id}: {self.throttle_ticks_applied} "
            "throttle tick(s) applied; a client told why can "
            "back off, a client that just sees latency retries "
            "harder"
        )
