"""Max poll records: fetch a batch small enough to process before the deadline.

A consumer polls, gets a batch of records, processes them, and
polls again, and it must call poll again within the max poll
interval or the group decides it is stuck and removes it. The
number of records a poll returns is therefore not just a throughput
knob, it is a deadline constraint: if a poll hands back more records
than the consumer can process before the interval elapses, the
consumer misses its next poll and is kicked out mid-batch, dropping
its partitions in a rebalance it caused. The safe batch size is the
interval divided by the per-record processing time, with a margin
so a few slow records do not push it over, and the calculator
computes that ceiling so an operator sets max poll records from the
processing cost rather than a copied default. The subtlety is that
the danger scales with processing time, not record count in the
abstract: a consumer doing heavy work per record, a database write
or an external call, can safely poll only a small batch, while one
doing trivial work can poll a large one, so the same max poll
records that is safe for a light consumer kicks a heavy one. The
calculator refuses a per-record time at or above the whole interval,
because a single record that alone takes longer than the interval
means no batch size is safe and the fix is faster processing or a
longer interval, not a smaller batch. The report states the head-
room the configured batch leaves against the interval, because a
batch sized right at the limit is one slow record away from a kick,
and the margin is what keeps a normal slowdown from becoming a
rebalance.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class PollBudget:
    poll_interval: int
    per_record_time: float
    margin: float = 0.2

    def __post_init__(self) -> None:
        if self.per_record_time <= 0:
            raise Invalid("per-record time must be positive")
        if self.per_record_time >= self.poll_interval:
            raise Invalid(
                "a single record takes at least the whole interval; no "
                "batch size is safe, the fix is faster processing or a "
                "longer interval, not a smaller batch"
            )
        if not 0 <= self.margin < 1:
            raise Invalid("margin must be in [0, 1)")

    def safe_max_records(self) -> int:
        usable = self.poll_interval * (1 - self.margin)
        return max(1, int(usable / self.per_record_time))

    def would_kick(self, configured: int) -> bool:
        return configured * self.per_record_time > self.poll_interval

    def headroom(self, configured: int) -> str:
        cost = configured * self.per_record_time
        if cost > self.poll_interval:
            over = cost - self.poll_interval
            return (
                f"batch of {configured} takes {cost:.0f} > interval "
                f"{self.poll_interval}, over by {over:.0f}; the "
                "consumer is kicked mid-batch, a rebalance it caused"
            )
        slack = self.poll_interval - cost
        return (
            f"batch of {configured} takes {cost:.0f} of "
            f"{self.poll_interval}, {slack:.0f} headroom; a batch at "
            "the limit is one slow record from a kick"
        )
