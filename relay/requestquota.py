"""Request quota: some clients cost CPU, not bytes, and that needs its own cap.

The byte quotas cap how much data a client produces or fetches, but
a client can overload a broker without moving many bytes: a flood
of tiny requests, a metadata refresh in a tight loop, a fetch that
asks about thousands of partitions each returning nothing. The cost
of these is CPU on the request-handler threads, not bandwidth, so a
byte quota does not see them, and the request quota exists for
exactly this dimension. It is expressed as a percentage of a
request thread's time, so a client allowed fifty percent may keep
half of one handler thread busy, and the broker measures the time
spent handling that client's requests over a window and throttles
when the client exceeds its share. The throttle is a delay, not a
drop: the broker computes how long the client must pause for its
recent usage to fall back under the allowance and holds the
response for that long, so the client naturally slows without
losing requests or connections. The calculator turns measured
thread-time into that delay: usage over the allowance means a
positive delay proportional to the overage, and usage within it
means no delay. The quota refuses an allowance percentage over the
total thread capacity, because promising a client more thread time
than the broker has is a misconfiguration that would never
throttle. The report states the client's thread-time share against
its allowance, because a broker CPU-bound with low bandwidth is
usually one client's small-request flood, invisible on a bytes
dashboard and obvious on this one.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class RequestQuota:
    allowance_pct: float
    thread_capacity_pct: float = 100.0

    def __post_init__(self) -> None:
        if self.allowance_pct <= 0:
            raise Invalid("the allowance must be positive")
        if self.allowance_pct > self.thread_capacity_pct:
            raise Invalid(
                "the allowance exceeds the broker's thread capacity; "
                "promising more thread time than exists never throttles"
            )

    def throttle_ticks(self, used_pct: float, window_ticks: int) -> int:
        if used_pct <= self.allowance_pct:
            return 0
        overage = used_pct - self.allowance_pct
        return int(window_ticks * overage / self.allowance_pct)

    def evaluate(self, used_pct: float, window_ticks: int) -> str:
        delay = self.throttle_ticks(used_pct, window_ticks)
        if delay == 0:
            return (
                f"within quota: used {used_pct:.0f}% of a thread, "
                f"allowance {self.allowance_pct:.0f}%, no throttle"
            )
        return (
            f"throttled {delay} tick(s): used {used_pct:.0f}% against "
            f"a {self.allowance_pct:.0f}% allowance; a CPU flood of "
            "small requests, invisible on a bytes dashboard"
        )
