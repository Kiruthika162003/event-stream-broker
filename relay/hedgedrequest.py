"""Hedged request: race a backup when the first is slow, but only when it is slow.

Tail latency, the slow few percent of requests, often comes not
from a slow system but from a slow moment on one replica, a garbage
collection pause, a disk hiccup, and the same request sent to a
different replica would have been fast. Hedging exploits that: send
the request to one replica, and if it has not answered within a
hedge delay, send a second copy to another replica and take
whichever answers first, cancelling the other. Because the slow
moment is usually on one replica and not the next, the hedge
usually wins, cutting the tail without changing the median. The
whole design rests on the hedge delay being high, set at a tail
percentile like the ninety-fifth, so that the fast majority of
requests answer before the delay and are never hedged, and only the
slow tail triggers a second copy. A hedge delay set too low hedges
most requests, roughly doubling the load on the cluster to shave a
tail that was not that bad, which is the failure mode of naive
hedging, so the delay is the knob that keeps the extra load small.
The model decides whether to hedge given how long the first request
has waited against the hedge delay, tracks that a response cancels
the outstanding copy, and estimates the extra load from the
fraction of requests expected to exceed the delay. It refuses a
hedge delay of zero, which hedges every request and doubles the
load outright, and refuses to hedge a request that already got a
response, a pointless second copy. It reports the expected hedge
rate from the delay's percentile, because a hedge rate far above a
few percent is a delay set too low, spending load on requests that
would have answered soon anyway rather than on the genuine tail.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class HedgePolicy:
    hedge_delay: int
    responded: bool = False
    hedged: bool = False

    def __post_init__(self) -> None:
        if self.hedge_delay < 1:
            raise Invalid(
                "a zero hedge delay hedges every request and doubles the load"
            )

    def should_hedge(self, waited: int) -> bool:
        return not self.responded and waited >= self.hedge_delay

    def hedge(self, waited: int) -> str:
        if self.responded:
            raise Invalid("the request already got a response; a hedge is pointless")
        if waited < self.hedge_delay:
            raise Invalid(
                f"waited {waited} < hedge delay {self.hedge_delay}; the fast "
                "majority answer before this and must not be hedged"
            )
        self.hedged = True
        return "hedged to a second replica; first answer wins, cancel the other"

    def respond(self) -> str:
        self.responded = True
        extra = " (the hedge copy is cancelled)" if self.hedged else ""
        return f"response taken{extra}"

    def expected_hedge_rate(self, fraction_over_delay: float) -> str:
        pct = fraction_over_delay * 100
        note = f"~{pct:.0f}% of requests exceed the delay and get hedged"
        if fraction_over_delay > 0.1:
            return note + "; far above a few percent means the delay is too low"
        return note + "; a small tail, the intended use"
