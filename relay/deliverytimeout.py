"""Delivery timeout: the promise a producer can actually make to its caller.

A producer's retries are bounded by a count in the naive design,
and a count is the wrong unit. Five retries with exponential
backoff can span a second or a minute depending on the backoff,
so a caller told "we retry five times" has no idea how long its
record might be in flight, and a record in flight is a record
whose fate the caller cannot report to its own user. The
delivery timeout replaces the count with a wall-clock bound: a
record is retried, with backoff, until it either succeeds or the
delivery timeout expires, whichever comes first, and the timeout
is the single number the producer can honestly hand its caller,
because it is the maximum time between calling send and getting
a final answer. The final answer is always definitive: success
with an offset, or failure with the last error, never the
silent limbo of a record that is neither confirmed nor abandoned.
The backoff still applies within the window, so a struggling
broker is not hammered, but the window, not the retry count, is
what ends the attempt, because the caller budgets in seconds and
the broker should speak the caller's language.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class DeliveryAttempt:
    delivery_timeout: int
    base_backoff: int
    started_at: int
    attempts: int = 0
    resolved: bool = False
    outcome: str = ""
    backoffs: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.delivery_timeout < 1 or self.base_backoff < 1:
            raise Invalid(
                "delivery timeout and backoff must be positive"
            )

    def _next_backoff(self) -> int:
        return self.base_backoff * (2 ** (self.attempts - 1))

    def try_send(self, now: int, succeeded: bool) -> str:
        if self.resolved:
            raise Invalid("this delivery already resolved")
        self.attempts += 1
        if succeeded:
            self.resolved = True
            self.outcome = "delivered"
            return (
                f"delivered on attempt {self.attempts} at {now}"
            )
        elapsed = now - self.started_at
        backoff = self._next_backoff()
        if elapsed + backoff >= self.delivery_timeout:
            self.resolved = True
            self.outcome = "failed"
            return (
                f"failed after {self.attempts} attempt(s): the "
                f"delivery timeout of {self.delivery_timeout} "
                "would expire before the next retry; a final "
                "answer, never silent limbo"
            )
        self.backoffs.append(backoff)
        return (
            f"attempt {self.attempts} failed, retrying after "
            f"{backoff} tick(s), within the delivery window"
        )

    def is_final(self) -> bool:
        return self.resolved
