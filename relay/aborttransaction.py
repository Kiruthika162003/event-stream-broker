"""Abort transaction: the records stay in the log, the consumer filters them out.

Aborting a transaction does not remove the records it already wrote.
They were appended to the log as they were produced, interleaved with
records from other producers, and rewriting the log to physically
excise them would be far too expensive on the hot path. Instead the
broker appends an abort marker, a control record that closes the
transaction, and remembers the transaction in an aborted index: the
producer id and the first offset the transaction wrote. The records
themselves remain physically present, and it becomes the read-
committed consumer's job to skip them. When such a consumer fetches a
range, the broker hands it the records together with the list of
aborted transactions overlapping that range, and the consumer drops
every record whose producer id matches an aborted transaction from
that transaction's first offset onward. A read-uncommitted consumer
ignores the aborted index entirely and sees everything, which is the
difference between the two isolation levels made concrete. The subtle
correctness point is that an abort applies only to a specific
producer's records from a specific offset, so a record from a
different producer at the same offset range, or a record from the same
producer before the aborted transaction began, must not be filtered;
the index keys on producer id and start offset precisely to avoid
dropping the innocent. The tracker records aborted transactions,
filters a batch of records for a read-committed consumer, passes the
batch through untouched for a read-uncommitted one, and refuses to
record an abort whose first offset is negative. It reports how many
records a filter dropped, because a topic where aborts drop a large
fraction of what is read is one paying a heavy tax for transactions
that mostly roll back."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class AbortedTransactions:
    # producer id -> first offset of its aborted transaction
    aborted: dict[str, int] = field(default_factory=dict)

    def record_abort(self, producer_id: str, first_offset: int) -> None:
        if first_offset < 0:
            raise Invalid("an aborted transaction's first offset cannot be negative")
        self.aborted[producer_id] = first_offset

    def _is_aborted(self, producer_id: str, offset: int) -> bool:
        start = self.aborted.get(producer_id)
        return start is not None and offset >= start

    def filter_for_read_committed(
        self, records: list[tuple[int, str]]
    ) -> list[tuple[int, str]]:
        # records are (offset, producer_id); drop those from aborted producers
        return [
            (offset, pid)
            for offset, pid in records
            if not self._is_aborted(pid, offset)
        ]

    def filter_for_read_uncommitted(
        self, records: list[tuple[int, str]]
    ) -> list[tuple[int, str]]:
        # read-uncommitted ignores the aborted index and sees everything
        return list(records)

    def dropped_count(self, records: list[tuple[int, str]]) -> int:
        return len(records) - len(self.filter_for_read_committed(records))

    def note(self, records: list[tuple[int, str]]) -> str:
        dropped = self.dropped_count(records)
        total = len(records) or 1
        return (
            f"{dropped}/{len(records)} record(s) dropped by the aborted index "
            f"({dropped / total * 100:.0f}%); a high fraction is a topic paying "
            "a heavy tax for transactions that mostly roll back"
        )
