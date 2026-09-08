"""Log truncation: drop a follower's divergent tail, never below the watermark.

A follower that took records from a leader which then failed may hold
a tail the new leader never had, records from a branch that lost the
election, and to rejoin it must drop that tail down to the offset
where its log and the new leader's agree. That offset comes from the
leader epoch comparison; truncation is the act of applying it. The act
has a hard floor: the high watermark, the offset up to which records
are committed and acknowledged to producers. Truncating at or above
the watermark drops only uncommitted records, which is exactly the
point, but truncating below it would throw away committed records that
the cluster has promised are durable, turning a routine follower
rejoin into silent data loss. So truncation below the high watermark
must be refused, always, no matter what offset the caller passes,
because that floor is the whole difference between correct recovery
and corruption. Truncation above the current log end is a no-op, there
is nothing past the end to drop, and it is reported as such rather
than treated as an error, since a follower already at or behind the
target simply has no divergent tail. The truncator holds the log
start, high watermark, and log end, drops everything above a target
offset, refuses a target below the watermark and below the log start,
and returns how many records were dropped. It reports the resulting
log end against the watermark, because the gap between them is the
uncommitted tail a follower may still lose on the next leadership
change, the records that were written but never promised."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class LogTruncation:
    log_start: int
    high_watermark: int
    log_end: int

    def __post_init__(self) -> None:
        if not self.log_start <= self.high_watermark <= self.log_end:
            raise Invalid(
                "the log must satisfy start <= high watermark <= end; "
                f"got start {self.log_start}, hw {self.high_watermark}, "
                f"end {self.log_end}"
            )

    def truncate_to(self, target: int) -> int:
        if target < self.high_watermark:
            raise Invalid(
                f"target {target} is below the high watermark "
                f"{self.high_watermark}; truncating there would drop committed "
                "records the cluster promised are durable, silent data loss"
            )
        if target < self.log_start:
            raise Invalid(
                f"target {target} is below the log start {self.log_start}"
            )
        if target >= self.log_end:
            # nothing past the end to drop; a follower with no divergent tail
            return 0
        dropped = self.log_end - target
        self.log_end = target
        return dropped

    def uncommitted_tail(self) -> int:
        return self.log_end - self.high_watermark

    def note(self) -> str:
        return (
            f"log end {self.log_end}, high watermark {self.high_watermark}, "
            f"uncommitted tail {self.uncommitted_tail()}; that gap is the tail "
            "a follower may still lose on the next leadership change"
        )
