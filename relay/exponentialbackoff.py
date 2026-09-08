"""Exponential backoff: grow the retry delay, cap it, and jitter to avoid a herd.

A client that retries a failed request immediately, and keeps
retrying at a fixed interval, hammers a broker that is already
struggling and slows its recovery. Exponential backoff spaces the
retries out: the delay doubles with each attempt, so a transient blip
is retried quickly while a persistent outage is retried ever more
gently, backing off the pressure exactly when it is not helping. Two
refinements make it safe in a fleet. A cap bounds the delay, because
doubling without a ceiling reaches absurd waits after a dozen attempts
and a client should keep probing a recovering broker at some steady
floor rather than sleeping for an hour. And jitter, randomizing the
delay within its range, breaks up the thundering herd: without it,
every client that failed at the same instant, when a broker briefly
went down, retries at the same instant, doubling in lockstep, and
their synchronized waves of retries knock the broker over again each
time it recovers. Full jitter picks the actual delay uniformly between
zero and the current capped exponential bound, so the same failure
spreads the retries across the whole interval instead of stacking them
on its edge. The calculator computes the base exponential delay for an
attempt, caps it, and returns a jittered delay within the capped
bound, using an injected random source so the result is testable. It
refuses a negative attempt number and a non-positive base or cap. It
reports the capped ceiling for an attempt, the bound the jitter draws
under, because that ceiling is what an operator reasons about when
setting how patient a client should be with a broker that keeps
failing."
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class ExponentialBackoff:
    base_ms: float
    cap_ms: float
    _rand: Callable[[], float] = field(default=random.random)

    def __post_init__(self) -> None:
        if self.base_ms <= 0:
            raise Invalid("the base delay must be positive")
        if self.cap_ms < self.base_ms:
            raise Invalid("the cap must be at least the base delay")

    def ceiling_ms(self, attempt: int) -> float:
        if attempt < 0:
            raise Invalid("the attempt number cannot be negative")
        # the doubling delay, bounded by the cap
        return min(self.cap_ms, self.base_ms * (2**attempt))

    def delay_ms(self, attempt: int) -> float:
        # full jitter: uniform between zero and the capped ceiling
        return self._rand() * self.ceiling_ms(attempt)

    def note(self, attempt: int) -> str:
        return (
            f"attempt {attempt} draws a jittered delay under {self.ceiling_ms(attempt):.0f}ms; "
            "the ceiling is what an operator reasons about, and the jitter is "
            "what keeps a fleet from retrying in lockstep and herding the broker"
        )
