"""Aborted index: read-committed skips aborted batches without rewriting the log.

When a transaction aborts, its records are already written into
the log, because the producer wrote them before the abort was
decided, and rewriting the log to remove them would be far too
expensive, so the records stay and the reader is told to skip
them. The broker keeps an aborted-transaction index alongside the
segment, a list of producer-id and first-offset pairs marking
where each aborted transaction's records begin, and a read-
committed fetch ships this index with the records so the consumer
can drop the aborted ones as it reads. The skip is per producer:
a record belongs to an aborted transaction if its producer id has
an aborted entry whose range covers the record's offset, so the
reader tracks which producer ids are currently inside an aborted
transaction and filters their records until the transaction's end
marker. The index is pruned as the log start advances, because an
aborted transaction entirely below the log start can never be
returned again, so keeping its entry wastes memory the segment no
longer needs. The subtlety is that read-committed still reads the
aborted records off disk and transfers them, filtering on the
consumer side, so an aborted-heavy workload pays to read and ship
data it will discard, which is why frequent aborts are a
performance problem, not only a correctness footnote. The report
states how much of the fetched range was aborted, because a
consumer seeing low throughput needs to know it is reading mostly
records destined for the floor.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AbortedTxn:
    producer_id: int
    first_offset: int
    last_offset: int

    def covers(self, offset: int) -> bool:
        return self.first_offset <= offset <= self.last_offset


@dataclass
class AbortedIndex:
    entries: list[AbortedTxn] = field(default_factory=list)

    def record(self, txn: AbortedTxn) -> None:
        self.entries.append(txn)

    def is_aborted(self, producer_id: int, offset: int) -> bool:
        return any(
            e.producer_id == producer_id and e.covers(offset)
            for e in self.entries
        )

    def prune_below(self, log_start: int) -> int:
        before = len(self.entries)
        self.entries = [
            e for e in self.entries if e.last_offset >= log_start
        ]
        return before - len(self.entries)

    def filter_ratio(
        self, fetched: list[tuple[int, int]]
    ) -> str:
        if not fetched:
            return "nothing fetched; no aborted records to skip"
        dropped = sum(
            1 for pid, off in fetched if self.is_aborted(pid, off)
        )
        pct = dropped / len(fetched) * 100
        return (
            f"{dropped}/{len(fetched)} fetched record(s) aborted "
            f"({pct:.0f}%); read-committed reads and ships them "
            "then drops them, so a high ratio is throughput spent "
            "on records destined for the floor"
        )
