"""Retry budget: retries help until they become the outage themselves.

Retrying a failed request is usually right, but retries have a
failure mode that turns a small outage into a large one: when a
downstream slows, more requests fail, so more are retried, and the
retries add load to the downstream that is already struggling,
making it slower, failing more requests, retrying more, a feedback
loop that can keep a downstream down long after the original cause
passed. A retry budget breaks the loop by capping retries as a
fraction of the request traffic, so retries can absorb a normal
rate of transient failures but cannot themselves become a
significant share of the load. The budget is a ratio, say ten
percent: for every ten normal requests the client may issue one
retry, and once retries hit that fraction of traffic further
retries are refused and the failed request simply fails, protecting
the downstream from the amplification even though it means giving up
on some requests that a retry might have saved. This is the trade
the budget makes explicit: without it, retries are unbounded and a
struggling downstream is buried; with it, retries are bounded and
the downstream gets a chance to recover, at the cost of a few
requests that do not get their retry. The budget tracks requests
and retries over a window and permits a retry only while the retry
ratio is under the cap, refusing one that would push it over. It
refuses a ratio at or above one, which would let retries equal or
exceed the traffic, no cap at all, and a ratio at or below zero,
which forbids every retry including the ones that would harmlessly
succeed. It reports the current retry ratio against the cap,
because a budget consistently at its cap is a downstream failing
enough that retries are constantly maxed, the amplification the
budget is holding back rather than a healthy blip.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class RetryBudget:
    ratio: float
    requests: int = 0
    retries: int = 0

    def __post_init__(self) -> None:
        if not 0 < self.ratio < 1:
            raise Invalid(
                "the retry ratio must be in (0, 1); at 1 retries can equal "
                "the traffic, no cap, and at 0 no retry is ever allowed"
            )

    def record_request(self) -> None:
        self.requests += 1

    def allow_retry(self) -> bool:
        # a retry is allowed only while it keeps the ratio under the cap
        return (self.retries + 1) <= self.requests * self.ratio

    def retry(self) -> str:
        if not self.allow_retry():
            raise Invalid(
                f"retry budget exhausted at ratio {self.ratio}; the request "
                "fails rather than add to the amplification burying the "
                "downstream"
            )
        self.retries += 1
        return f"retry permitted; {self.retries} retries against {self.requests} requests"

    def current_ratio(self) -> str:
        if self.requests == 0:
            return "no requests yet"
        ratio = self.retries / self.requests
        return (
            f"retry ratio {ratio:.2f} against cap {self.ratio}; a budget "
            "always at its cap is a downstream failing enough that retries "
            "are maxed, the amplification being held back"
        )
