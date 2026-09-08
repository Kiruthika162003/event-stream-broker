"""Retry topic: a failed record waits in a slower lane before it is given up on.

A consumer that fails to process a record has a bad choice between
blocking the partition while it retries and dropping the record,
and the retry-topic pattern gives a third option: move the failed
record to a separate retry topic and let the main consumer move on,
so one poison record does not stall the healthy ones behind it. The
retry topics are tiered by delay, a fast lane retried after
seconds, a slower one after minutes, a slowest after an hour, and a
record that keeps failing escalates through them, waiting longer
between each attempt so a transient failure clears on an early tier
while a persistent one is not hammered every second. After the last
tier the record has failed enough times that further retries are
pointless, and it goes to the dead-letter topic for a human, the
terminal destination. This separates transient from permanent
failure by patience: most failures are transient and clear on a
fast tier, and only a record that survived every tier is treated as
permanently bad. The router advances a record to the next tier on
failure, computes the delay it waits there, and sends it to the
dead-letter once it has exhausted the tiers. It refuses a negative
attempt count, and it treats a record that succeeded on retry as
done rather than continuing to escalate it, because escalating a
now-succeeded record would reprocess and possibly duplicate it. The
report states which tier a record is on and the delay it implies,
because a pile-up on a slow tier is a persistent failure the
retries are only postponing, and knowing the tier tells an operator
whether to wait for the DLQ or investigate now.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid

DEAD_LETTER = "dead-letter"


@dataclass
class RetryRouter:
    tier_delays: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.tier_delays:
            raise Invalid("at least one retry tier is required")
        if any(d < 0 for d in self.tier_delays):
            raise Invalid("tier delays cannot be negative")

    def route_on_failure(self, attempt: int) -> str:
        if attempt < 0:
            raise Invalid("attempt count cannot be negative")
        if attempt >= len(self.tier_delays):
            return DEAD_LETTER
        return f"retry-tier-{attempt}"

    def delay_for(self, attempt: int) -> int:
        if attempt < 0 or attempt >= len(self.tier_delays):
            raise Invalid(
                f"tier {attempt} is outside the {len(self.tier_delays)} "
                "tiers; a dead-letter record has no retry delay"
            )
        return self.tier_delays[attempt]

    def on_success(self, attempt: int) -> str:
        return (
            f"record succeeded on tier {attempt}; done, not escalated, "
            "or escalating a succeeded record would reprocess it"
        )

    def report(self, attempt: int) -> str:
        dest = self.route_on_failure(attempt)
        if dest == DEAD_LETTER:
            return (
                f"attempt {attempt} exhausted all {len(self.tier_delays)} "
                "tiers; to the dead-letter for a human, a permanent failure"
            )
        return (
            f"on {dest}, waiting {self.delay_for(attempt)}; a pile-up here "
            "is a persistent failure the retries only postpone"
        )
