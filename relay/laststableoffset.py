"""Last stable offset: the ceiling a read-committed consumer may not read past.

A read-committed consumer must never see a record from a transaction
that has not committed, because that transaction might still abort and
the record would then have to be unread, which is impossible once
handed out. So a read-committed consumer does not read up to the high
watermark, the way a read-uncommitted consumer does. It reads up to the
last stable offset, the offset before the first record of the oldest
transaction that is still open. Every record below the last stable
offset belongs to a transaction whose fate is already decided,
committed or aborted, so the broker knows whether to deliver it or skip
it. Records at or above it belong to transactions still in flight,
whose outcome is unknown, and they are withheld until those
transactions resolve. This means a single long-running transaction
holds the last stable offset in place and blocks read-committed
consumers from advancing, even as the high watermark climbs far ahead
with committed data from other producers sitting just above the line,
visible to read-uncommitted consumers but not to read-committed ones,
the cost of the isolation. When the oldest open transaction commits or
aborts, the last stable offset jumps forward to the next open
transaction's start, or to the high watermark if none remain. The
tracker holds the high watermark and the open transactions by their
first offset, computes the last stable offset as the minimum of the
high watermark and the earliest open transaction's start, resolves a
transaction to advance it, and refuses an open at an offset above the
high watermark, since a transaction cannot start past records that do
not exist. It reports the gap between the high watermark and the last
stable offset, because that gap is committed data a read-committed
consumer cannot yet see, the lag a stuck transaction imposes on
everyone reading committed."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid, Missing


@dataclass
class LastStableOffset:
    high_watermark: int
    # first offset of each still-open transaction
    open_transactions: dict[str, int] = field(default_factory=dict)

    def begin(self, txn_id: str, first_offset: int) -> None:
        if first_offset > self.high_watermark:
            raise Invalid(
                f"transaction '{txn_id}' begins at {first_offset}, past the "
                f"high watermark {self.high_watermark}; it cannot start past "
                "records that do not exist"
            )
        self.open_transactions[txn_id] = first_offset

    def resolve(self, txn_id: str) -> None:
        if txn_id not in self.open_transactions:
            raise Missing(f"transaction '{txn_id}' is not open")
        del self.open_transactions[txn_id]

    def last_stable_offset(self) -> int:
        if not self.open_transactions:
            return self.high_watermark
        return min(self.high_watermark, *self.open_transactions.values())

    def is_visible_to_read_committed(self, offset: int) -> bool:
        return offset < self.last_stable_offset()

    def withheld_gap(self) -> int:
        return self.high_watermark - self.last_stable_offset()

    def note(self) -> str:
        return (
            f"last stable offset {self.last_stable_offset()}, high watermark "
            f"{self.high_watermark}, {self.withheld_gap()} record(s) withheld; "
            "that gap is committed data a read-committed consumer cannot yet "
            "see, the lag a stuck transaction imposes on everyone"
        )
