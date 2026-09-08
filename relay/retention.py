"""Retention: the log forgets on purpose, and says what it forgot.

A stream that never forgets is a database with worse query
support and a disk bill that only grows. Retention deletes
whole sealed segments by one of two policies: by age, drop
segments whose last record is older than the window, and by
size, drop oldest segments until the total fits the cap. The
policies compose by union, a segment leaves if either policy
condemns it, because the operator who sets both means "whichever
comes first" and a broker that required both would keep a
week of data on a disk sized for a day. The one invariant that
outranks every policy is the committed floor: a segment holding
records above any live consumer group's committed offset is
never dropped, because deleting data a consumer has not read
turns retention into data loss with a schedule. The report
names bytes reclaimed and, crucially, the reason a segment was
spared, since "kept for group billing at offset 4180" is an
answer and "still there" is a mystery.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid
from relay.segmentlog import SegmentLog


@dataclass(frozen=True)
class RetentionPolicy:
    max_age_ticks: int | None = None
    max_bytes: int | None = None

    def __post_init__(self) -> None:
        if self.max_age_ticks is None and self.max_bytes is None:
            raise Invalid(
                "a retention policy with no limit keeps "
                "everything forever, which is not retention"
            )
        if self.max_age_ticks is not None and self.max_age_ticks < 1:
            raise Invalid("the age window must be positive")
        if self.max_bytes is not None and self.max_bytes < 1:
            raise Invalid("the size cap must be positive")


@dataclass
class RetentionRun:
    policy: RetentionPolicy
    reclaimed_segments: int = 0
    reclaimed_bytes: int = 0

    def _age_condemns(
        self, segment_last_tick: int, now: int
    ) -> bool:
        if self.policy.max_age_ticks is None:
            return False
        return now - segment_last_tick > self.policy.max_age_ticks

    def apply(
        self,
        log: SegmentLog,
        segment_last_tick: dict[int, int],
        now: int,
        committed_floor: int,
    ) -> str:
        spared_reason = None
        while len(log.segments) > 1:
            oldest = log.segments[0]
            if not oldest.sealed:
                spared_reason = "the oldest segment is still active"
                break
            if oldest.next_offset() > committed_floor:
                spared_reason = (
                    f"kept: segment holds records above the "
                    f"committed floor {committed_floor}, and "
                    "dropping unread data is loss with a schedule"
                )
                break
            last_tick = segment_last_tick.get(
                oldest.base_offset, now
            )
            total_bytes = sum(
                s.size_bytes() for s in log.segments
            )
            age_out = self._age_condemns(last_tick, now)
            size_out = (
                self.policy.max_bytes is not None
                and total_bytes > self.policy.max_bytes
            )
            if not age_out and not size_out:
                spared_reason = (
                    "kept: within both the age window and the "
                    "size cap"
                )
                break
            self.reclaimed_bytes += oldest.size_bytes()
            self.reclaimed_segments += 1
            log.segments.pop(0)
        head = (
            f"reclaimed {self.reclaimed_segments} segment(s), "
            f"{self.reclaimed_bytes} byte(s)"
        )
        if spared_reason:
            return f"{head}; stopped: {spared_reason}"
        return head
