"""Compaction lag: not too soon, so consumers see it, not too late, so it is gone.

Log compaction keeps only the latest value per key, but when a
record becomes eligible to be compacted away is bounded on both
sides, and the two bounds serve opposite purposes. The minimum
compaction lag holds a record uncompacted for a while after it is
written, even if a newer value for its key already exists, so a
consumer reading the log has a window in which it can still see the
record before compaction removes it, which matters for a consumer
that must observe every update and not just the latest. Without a
minimum lag, a rapidly-updated key could have its intermediate
values compacted away before a consumer ever read them. The maximum
compaction lag is the opposite guarantee: a record must be
compacted within a bounded time, which is how a tombstone-based
deletion becomes a promise, if a key is deleted by writing a
tombstone, the maximum lag bounds how long the old value can still
linger before compaction removes it, the deadline a data-deletion
requirement depends on. A record's eligibility is thus a function
of its age: below the minimum lag it is not yet eligible, above the
maximum lag it is overdue and compaction is behind its deadline,
and in between it is eligible and compaction may take it when it
runs. The calculator classifies a record by age against the two
bounds and refuses a maximum lag below the minimum, an impossible
window where a record would be overdue before it was eligible. It
reports how long until a record becomes eligible or how overdue it
is, because a pile of overdue records is compaction falling behind
its deletion deadline, the signal that the cleaner is not keeping
up and a deletion promise is at risk.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

NOT_YET = "not-yet-eligible"
ELIGIBLE = "eligible"
OVERDUE = "overdue"


@dataclass(frozen=True)
class CompactionLag:
    min_lag: int
    max_lag: int

    def __post_init__(self) -> None:
        if self.min_lag < 0 or self.max_lag < 0:
            raise Invalid("lag bounds cannot be negative")
        if self.max_lag < self.min_lag:
            raise Invalid(
                "max lag below min lag is an impossible window; a record "
                "would be overdue before it was eligible"
            )

    def classify(self, age: int) -> str:
        if age < self.min_lag:
            return NOT_YET
        if age > self.max_lag:
            return OVERDUE
        return ELIGIBLE

    def status(self, age: int) -> str:
        state = self.classify(age)
        if state == NOT_YET:
            return (
                f"not eligible for {self.min_lag - age} more; the minimum "
                "lag keeps it visible to consumers first"
            )
        if state == OVERDUE:
            return (
                f"overdue by {age - self.max_lag}; compaction is behind its "
                "deadline and a deletion promise is at risk"
            )
        return f"eligible; compaction may take it, {self.max_lag - age} before overdue"
