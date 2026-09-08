"""Transactions: many partitions, one atomic verdict, visible all-or-none.

A producer that writes to three partitions and wants them to
appear together, or not at all, needs a transaction, and the
mechanism is a marker rather than a lock. The producer opens a
transaction, appends records to any partitions, and then writes
a commit or abort marker to every partition it touched; a
read-committed consumer skips records that belong to a
transaction not yet marked committed, so uncommitted records
are durable on the log but invisible, which is the whole trick:
atomicity without holding the log hostage. The state machine is
strict because half-applied transactions are the worst outcome:
a transaction can go open to committing to committed, or open to
aborting to aborted, and no other edge exists, so a commit after
an abort is refused rather than racing. The timeout fences the
zombie: a transaction open longer than its bound is force-aborted
so a producer that died mid-transaction cannot leave records
that block every read-committed consumer behind them forever.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid

OPEN = "open"
COMMITTING = "committing"
COMMITTED = "committed"
ABORTING = "aborting"
ABORTED = "aborted"

ALLOWED = {
    OPEN: {COMMITTING, ABORTING},
    COMMITTING: {COMMITTED},
    ABORTING: {ABORTED},
    COMMITTED: set(),
    ABORTED: set(),
}


@dataclass
class Transaction:
    txn_id: str
    opened_at: int
    timeout: int
    state: str = OPEN
    partitions_touched: set[int] = field(default_factory=set)
    records: list[tuple[int, int]] = field(default_factory=list)

    def append(self, partition: int, offset: int) -> None:
        if self.state != OPEN:
            raise Invalid(
                f"{self.txn_id} is {self.state}; records only "
                "join an open transaction"
            )
        self.partitions_touched.add(partition)
        self.records.append((partition, offset))

    def _transition(self, target: str) -> None:
        if target not in ALLOWED[self.state]:
            raise Invalid(
                f"{self.txn_id} cannot go {self.state} -> "
                f"{target}; a half-applied transaction is the "
                "worst outcome, so the edge does not exist"
            )
        self.state = target

    def commit(self) -> str:
        self._transition(COMMITTING)
        self._transition(COMMITTED)
        return (
            f"{self.txn_id} committed across "
            f"{len(self.partitions_touched)} partition(s); "
            "markers make the records visible together"
        )

    def abort(self) -> str:
        self._transition(ABORTING)
        self._transition(ABORTED)
        return (
            f"{self.txn_id} aborted; its records stay durable "
            "but invisible to read-committed consumers"
        )

    def force_abort_if_expired(self, now: int) -> str | None:
        if self.state == OPEN and now - self.opened_at > self.timeout:
            self.abort()
            return (
                f"{self.txn_id} force-aborted after "
                f"{now - self.opened_at} ticks open; a zombie's "
                "records will not block read-committed consumers "
                "forever"
            )
        return None


def visible_to_read_committed(
    records: list[tuple[int, int, str]],
) -> list[tuple[int, int]]:
    return [
        (partition, offset)
        for partition, offset, state in records
        if state == COMMITTED
    ]
