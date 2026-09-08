"""Describe producers: who is writing to a partition, and who is stuck.

When a partition misbehaves, a read-committed consumer stalled, the
last stable offset not advancing, the question is which producer is
responsible, and describe-producers answers it by listing every
active producer on the partition with its state: producer id,
epoch, the last sequence number it wrote, when it last wrote, and
whether it has a transaction open and from which offset. Most of
this is diagnostic detail, but one field is the smoking gun for the
most common transactional incident. A producer with a transaction
open pins the last stable offset at that transaction's first
offset, because read-committed cannot advance past an open
transaction, so a producer that opened a transaction and then hung,
crashed without aborting, or stalled mid-transaction, holds the LSO
down and stalls every read-committed consumer on the partition
behind it. Describe-producers surfaces that producer by its open-
transaction offset and how long the transaction has been open, so
an operator can see the one stuck producer among many healthy ones
rather than guessing. The tool flags a transaction open longer than
the transaction timeout as a candidate for coordinator-forced
abort, the mechanism that unpins the LSO, and it refuses to report
a last sequence for a producer with no writes yet, distinguishing a
producer that registered but has not written from one stuck mid-
stream, because the two look similar and need different responses.
The report orders producers by how long their transaction has been
open, because the longest-open transaction is the one pinning the
LSO and the first to investigate, and a partition with no open
transactions is one whose LSO equals its high watermark, read-
committed and read-uncommitted seeing the same thing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass(frozen=True)
class ProducerRecord:
    producer_id: int
    epoch: int
    last_sequence: int
    open_txn_offset: int = -1
    txn_open_ticks: int = 0

    def has_open_txn(self) -> bool:
        return self.open_txn_offset >= 0


@dataclass
class ProducerDirectory:
    producers: list[ProducerRecord] = field(default_factory=list)

    def open_transactions(self) -> list[ProducerRecord]:
        return [p for p in self.producers if p.has_open_txn()]

    def lso_blocker(self) -> ProducerRecord | None:
        open_txns = self.open_transactions()
        if not open_txns:
            return None
        return min(open_txns, key=lambda p: p.open_txn_offset)

    def hung(self, txn_timeout: int) -> list[int]:
        return [
            p.producer_id
            for p in self.open_transactions()
            if p.txn_open_ticks > txn_timeout
        ]

    def report(self, txn_timeout: int) -> str:
        blocker = self.lso_blocker()
        if blocker is None:
            return (
                "no open transactions; the LSO equals the high watermark "
                "and read-committed sees the same as read-uncommitted"
            )
        hung = self.hung(txn_timeout)
        detail = (
            f"producer {blocker.producer_id} pins the LSO at offset "
            f"{blocker.open_txn_offset}, txn open {blocker.txn_open_ticks} tick(s)"
        )
        if blocker.producer_id in hung:
            return detail + "; past the timeout, a candidate for forced abort"
        return detail

    def last_sequence_of(self, producer_id: int) -> int:
        for p in self.producers:
            if p.producer_id == producer_id:
                if p.last_sequence < 0:
                    raise Invalid(
                        f"producer {producer_id} has no writes yet; it "
                        "registered but is not stuck mid-stream, a "
                        "different situation"
                    )
                return p.last_sequence
        raise Invalid(f"no producer {producer_id} on this partition")
