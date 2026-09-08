"""Token bucket: a burst is allowed, then the rate is the refill, not the peak.

The sliding-window quota elsewhere in this package measures bytes
over a trailing window and throttles when the window's total gets
too high, which is fair over the window but unforgiving of a short
burst: a client that is quiet for a while and then sends a batch is
throttled on the batch even though its average is well under the
limit. A token bucket takes the opposite stance on bursts. The
bucket holds up to a capacity of tokens and refills at a steady
rate, a request spends tokens equal to its size, and it proceeds if
the bucket has enough and waits otherwise, so a client that saved
up tokens while idle can spend them in a burst up to the bucket's
capacity, and only once the bucket drains does its throughput fall
to the refill rate. This makes the two knobs mean different things:
the refill rate is the sustained throughput and the capacity is how
large a burst is forgiven, so an operator sets capacity to the
largest burst worth absorbing and rate to the load the disk can
take continuously. The bucket refuses a request larger than its
capacity outright, because such a request can never be satisfied no
matter how long it waits, the bucket cannot hold enough tokens for
it, and making it wait forever would be a worse answer than
rejecting it as misconfigured. Refill is computed from elapsed time
rather than a background timer, so the bucket is exact regardless of
how often it is polled, and it never fills past capacity, because
tokens that would overflow are throughput the client did not use
and cannot bank beyond the burst the capacity already allows.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class TokenBucket:
    capacity: float
    refill_per_tick: float
    tokens: float = -1.0
    last_tick: int = 0

    def __post_init__(self) -> None:
        if self.capacity <= 0 or self.refill_per_tick <= 0:
            raise Invalid("capacity and refill rate must be positive")
        if self.tokens < 0:
            self.tokens = self.capacity

    def _refill(self, now: int) -> None:
        if now < self.last_tick:
            raise Invalid("time went backwards; refill needs a monotonic clock")
        elapsed = now - self.last_tick
        self.tokens = min(
            self.capacity, self.tokens + elapsed * self.refill_per_tick
        )
        self.last_tick = now

    def take(self, now: int, size: float) -> str:
        if size > self.capacity:
            raise Invalid(
                f"a request of {size} exceeds the bucket capacity "
                f"{self.capacity}; it can never be satisfied and "
                "waiting forever is worse than rejecting it"
            )
        self._refill(now)
        if self.tokens >= size:
            self.tokens -= size
            return f"served {size}; {self.tokens:.1f} token(s) left"
        deficit = size - self.tokens
        wait = deficit / self.refill_per_tick
        return (
            f"throttled {size}: short {deficit:.1f} token(s), wait "
            f"~{wait:.1f} tick(s); the burst is spent and throughput "
            "now falls to the refill rate"
        )
