"""Backoff with jitter: retries that recover without a thundering herd.

When a broker fails, every client connected to it retries, and if
they all retry on the same schedule they arrive together, a
synchronized wave that hits the recovering broker at the exact
moment it is weakest and knocks it back down, so the outage
oscillates instead of ending. Exponential backoff spreads retries
in time, doubling the wait after each failure so a persistently
failing endpoint is polled ever less often, which protects the
broker but does not by itself desynchronize the clients: a
thousand clients that all started backing off at the same failure
still double in lockstep and still arrive together, just at wider
intervals. Jitter is the fix that the exponential part alone
misses, randomizing each client's wait within its backoff window
so the wave smears into a spread, and the model shows why full
jitter, a uniform random pick from zero to the current ceiling,
desynchronizes better than the exponential schedule alone even
though it sometimes retries sooner. The backoff also caps, because
unbounded doubling eventually means a client that waits an hour to
retry an endpoint that recovered fifty-nine minutes ago, so the
ceiling bounds the worst-case recovery latency. The calculator
returns the window and a jittered sample within it, and reports
the spread a fleet of clients would produce, because the whole
value of jitter is a number invisible in a single client and
obvious across a thousand: the difference between one wave and a
smooth arrival.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class BackoffPolicy:
    base: int
    ceiling: int

    def __post_init__(self) -> None:
        if self.base < 1 or self.ceiling < self.base:
            raise Invalid(
                "base positive and ceiling at least the base"
            )

    def window(self, attempt: int) -> int:
        if attempt < 0:
            raise Invalid("attempt is nonnegative")
        return min(self.ceiling, self.base * (2**attempt))

    def jittered(self, attempt: int, roll: float) -> int:
        if not 0 <= roll <= 1:
            raise Invalid("the jitter roll is a fraction in [0,1]")
        return int(self.window(attempt) * roll)


def spread_of_fleet(
    policy: BackoffPolicy, attempt: int, rolls: list[float]
) -> str:
    if not rolls:
        raise Invalid("no clients to spread")
    samples = [policy.jittered(attempt, r) for r in rolls]
    spread = max(samples) - min(samples)
    window = policy.window(attempt)
    return (
        f"attempt {attempt}: window {window}, {len(rolls)} "
        f"client(s) spread across {spread} tick(s); without "
        "jitter all would arrive at once, the wave that knocks a "
        "recovering broker back down"
    )
