"""The log cleaner: compact the dirtiest logs first, and know when to stop.

Compaction is not free, it rewrites segments, so a broker with
limited cleaner bandwidth cannot compact everything continuously
and must choose. The cleaner ranks partitions by dirty ratio,
the fraction of records that are superseded and therefore
reclaimable, and compacts the dirtiest first, because a log that
is ninety percent stale updates yields far more space per unit of
cleaner work than one that is ten percent stale. The ratio is the
right metric precisely because it is scale-free: a tiny log that
is entirely garbage and a huge log that is entirely garbage are
equally worth cleaning per byte processed, and ranking by
absolute reclaimable bytes would starve small hot logs behind
large cold ones. The cleaner also respects a minimum dirty ratio
below which it does not bother, because compacting a log that is
two percent dirty spends more work than it reclaims, and a
cleaner that chases tiny gains is a cleaner competing with the
live traffic for no real benefit. The report states cleaner work
spent against space reclaimed, because a cleaner is only earning
its bandwidth when that ratio is favorable, and a cleaner running
flat out while reclaiming little is a misconfiguration wearing
the costume of diligence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass(frozen=True)
class DirtyLog:
    partition: int
    total_records: int
    superseded_records: int

    def __post_init__(self) -> None:
        if self.total_records < 1:
            raise Invalid("an empty log has no dirty ratio")
        if self.superseded_records > self.total_records:
            raise Invalid(
                "more superseded than total is impossible"
            )

    def dirty_ratio(self) -> float:
        return self.superseded_records / self.total_records


@dataclass
class LogCleaner:
    min_dirty_ratio: float
    work_spent: int = 0
    records_reclaimed: int = 0
    logs_cleaned: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not 0 < self.min_dirty_ratio < 1:
            raise Invalid(
                "the minimum dirty ratio is a fraction between "
                "0 and 1"
            )

    def rank(self, logs: list[DirtyLog]) -> list[DirtyLog]:
        eligible = [
            log
            for log in logs
            if log.dirty_ratio() >= self.min_dirty_ratio
        ]
        return sorted(
            eligible,
            key=lambda log: (-log.dirty_ratio(), log.partition),
        )

    def clean(self, log: DirtyLog) -> str:
        if log.dirty_ratio() < self.min_dirty_ratio:
            return (
                f"partition {log.partition} at "
                f"{log.dirty_ratio():.0%} dirty is below the "
                f"{self.min_dirty_ratio:.0%} floor; skipped, "
                "because chasing tiny gains competes with live "
                "traffic for nothing"
            )
        self.work_spent += log.total_records
        self.records_reclaimed += log.superseded_records
        self.logs_cleaned.append(log.partition)
        return (
            f"partition {log.partition} compacted, reclaimed "
            f"{log.superseded_records} of {log.total_records} "
            "records"
        )

    def efficiency(self) -> str:
        if self.work_spent == 0:
            raise Invalid("no cleaner work to rate")
        ratio = self.records_reclaimed / self.work_spent
        return (
            f"{self.records_reclaimed} reclaimed for "
            f"{self.work_spent} processed ({ratio:.0%}); a "
            "cleaner running flat out while reclaiming little is "
            "a misconfiguration in the costume of diligence"
        )
