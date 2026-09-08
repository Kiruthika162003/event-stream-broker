"""Commit retry: a failed offset commit is retryable, except when it is not.

Committing an offset can fail, and whether to retry depends
entirely on why, so a commit-retry that treats all failures alike
either gives up on transient errors or loops forever on permanent
ones. The retry classifier distinguishes three cases. A network
timeout or a coordinator-loading error is transient: the commit
may have succeeded or not, and retrying is safe because offset
commits are idempotent, the same offset committed twice is the
same result, so retry with backoff. A coordinator-moved error is
not a failure to retry against the same broker, it is a redirect:
the retry must go to the new coordinator, and retrying against
the old one loops forever, so the classifier routes it rather
than counting it as an attempt. An illegal-generation error is
permanent for this commit: the group rebalanced, the assignment
this commit was based on is gone, and retrying cannot succeed
because the offset belongs to an assignment that no longer
exists, so the commit is abandoned and the consumer rejoins. The
danger the classifier guards against is retrying the permanent
case, because a consumer looping on illegal-generation is a
consumer stuck forever committing against a dead assignment, busy
and making no progress, the worst failure because it looks like
work. The report counts retries by cause, because a rising
transient count is a flaky network while a rising illegal-
generation count is a group rebalancing too often.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

TRANSIENT = "transient"
COORDINATOR_MOVED = "coordinator-moved"
ILLEGAL_GENERATION = "illegal-generation"


@dataclass
class CommitRetrier:
    max_retries: int
    transient_retries: int = 0
    redirects: int = 0
    abandoned: int = 0

    def __post_init__(self) -> None:
        if self.max_retries < 1:
            raise Invalid("at least one retry must be allowed")

    def on_failure(
        self, cause: str, attempt: int
    ) -> str:
        if cause == TRANSIENT:
            if attempt >= self.max_retries:
                self.abandoned += 1
                return (
                    "transient retries exhausted; abandoned after "
                    f"{attempt} attempt(s), the caller decides "
                    "next"
                )
            self.transient_retries += 1
            return (
                f"transient: retry {attempt + 1} with backoff, "
                "safe because offset commits are idempotent"
            )
        if cause == COORDINATOR_MOVED:
            self.redirects += 1
            return (
                "coordinator moved: route to the new coordinator, "
                "not a retry against the old one which loops "
                "forever"
            )
        if cause == ILLEGAL_GENERATION:
            self.abandoned += 1
            return (
                "illegal generation: abandon and rejoin; "
                "retrying commits against a dead assignment "
                "forever, busy and making no progress"
            )
        raise Invalid(f"unknown commit failure cause {cause}")

    def report(self) -> str:
        return (
            f"{self.transient_retries} transient retry(ies), "
            f"{self.redirects} redirect(s), {self.abandoned} "
            "abandoned; rising transients are a flaky network, "
            "rising illegal-generation is a group rebalancing too "
            "often"
        )
