"""An exactly-once day: idempotent produce, a transaction, isolation, the loop.

Run with: python -m examples.exactlyonceday
"""

from __future__ import annotations

from relay.ctp import ProcessingTransaction
from relay.idempotent import IdempotencyGate
from relay.isolation import (
    READ_COMMITTED,
    PartitionOffsets,
    readable_ceiling,
)
from relay.txncoordinator import TransactionCoordinator


def morning_the_idempotent_produce():
    gate = IdempotencyGate()
    gate.open_session("p", epoch=1)
    plan = [0, 1, 2, 0, 1, 2, 3]
    accepted = duplicates = 0
    offset = 100
    for seq in plan:
        if gate.admit("p", 1, seq, offset).startswith("accepted"):
            accepted += 1
            offset += 1
        else:
            duplicates += 1
    print(
        f"morning: {accepted} accepted, {duplicates} duplicates "
        "absorbed before any consumer saw them"
    )


def midday_the_coordinator():
    coord = TransactionCoordinator()
    coord.register("payer")
    coord.begin("payer", 0)
    print(f"midday:  {coord.complete('payer', 0, commit=True)}")


def afternoon_the_loop():
    txn = ProcessingTransaction(exactly_once=True)
    txn.begin()
    txn.produce("output", 0)
    txn.commit_offset("g", 0, 500)
    print(f"afternoon: {txn.commit()}")


def evening_the_isolation():
    offsets = PartitionOffsets(
        high_watermark=1000, last_stable_offset=940
    )
    ceiling, _ = readable_ceiling(READ_COMMITTED, offsets)
    print(
        f"evening: read-committed stops at {ceiling}, sixty "
        "records short of the watermark and safe from an abort"
    )


def main() -> int:
    morning_the_idempotent_produce()
    midday_the_coordinator()
    afternoon_the_loop()
    evening_the_isolation()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
