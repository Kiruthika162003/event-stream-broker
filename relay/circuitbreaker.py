"""Circuit breaker: stop calling what is failing, and test before trusting again.

A client calling a downstream that has started failing, a producer
whose broker is down, a connector whose sink is unreachable, faces
a choice on every call: try again and add load to something already
struggling, or stop and fail fast. A circuit breaker automates the
choice with three states. Closed is normal: calls pass through, and
failures are counted. When failures cross a threshold the breaker
opens, and in the open state calls fail immediately without even
attempting the downstream, which both spares the client the timeout
wait and spares the downstream the load, letting it recover instead
of being hammered while it is down. After a cooldown the breaker
goes half-open and lets a single trial call through: if it succeeds
the downstream has recovered and the breaker closes, and if it fails
the breaker opens again for another cooldown, so recovery is tested
with one call rather than assumed or flooded. The value is in the
open state's fast failure: without a breaker, every call to a dead
downstream waits its full timeout, so a burst of calls ties up the
client's threads waiting on something that will not answer, turning
a downstream outage into a client outage, and the breaker cuts that
by failing instantly once it is open. The breaker refuses a call in
the open state before the cooldown elapses, the fast-fail that is
the point, and allows exactly one trial in half-open, refusing
concurrent trials that would flood a downstream that has not proven
it recovered. It reports the state and, in open, how long until the
half-open trial, because a breaker stuck open is a downstream that
has not recovered across several cooldowns, a longer outage than a
transient blip.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

CLOSED = "closed"
OPEN = "open"
HALF_OPEN = "half-open"


@dataclass
class CircuitBreaker:
    threshold: int
    cooldown: int
    state: str = CLOSED
    failures: int = 0
    opened_at: int = -1

    def __post_init__(self) -> None:
        if self.threshold < 1 or self.cooldown < 1:
            raise Invalid("threshold and cooldown must be positive")

    def _maybe_half_open(self, now: int) -> None:
        if self.state == OPEN and now - self.opened_at >= self.cooldown:
            self.state = HALF_OPEN

    def allow(self, now: int) -> str:
        self._maybe_half_open(now)
        if self.state == OPEN:
            wait = self.cooldown - (now - self.opened_at)
            raise Invalid(
                f"circuit open; failing fast, {wait} until the half-open "
                "trial, sparing the downstream the load it needs to recover"
            )
        return f"call allowed in {self.state}"

    def on_success(self, now: int) -> str:
        self._maybe_half_open(now)
        self.state = CLOSED
        self.failures = 0
        return "success; circuit closed"

    def on_failure(self, now: int) -> str:
        if self.state == HALF_OPEN:
            self.state = OPEN
            self.opened_at = now
            return "trial failed; circuit re-opened for another cooldown"
        self.failures += 1
        if self.failures >= self.threshold:
            self.state = OPEN
            self.opened_at = now
            return f"threshold {self.threshold} hit; circuit opened, failing fast"
        return f"failure {self.failures}/{self.threshold}; still closed"
