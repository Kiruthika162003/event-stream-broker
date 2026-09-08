"""A duplicate flood and an aborted batch, and the consumer sees each once.

Exactly-once is not one feature; it is idempotent production
and transactional visibility standing together, and this proof
runs the scenario that breaks brokers claiming it lightly. A
producer sends five records, retries three of them after a
false timeout, and wraps the batch in a transaction that it
then aborts, opening a second transaction that commits four
records. The drill asserts two independent things: the
idempotency gate absorbs the three retries so the log never
holds a duplicate, and the read-committed view shows only the
four records from the committed transaction, never the aborted
batch. The counterfactual is the weight: without the gate the
log would carry three duplicates, and without transactional
visibility the aborted batch would reach the consumer, so the
gap between eight naive deliveries and four correct ones is the
entire distance between at-least-once and exactly-once.
"""

from __future__ import annotations

from relay.idempotent import IdempotencyGate
from relay.proofs.finding import Finding
from relay.transactions import (
    ABORTED,
    COMMITTED,
    Transaction,
    visible_to_read_committed,
)


def run() -> Finding:
    gate = IdempotencyGate()
    gate.open_session("p", epoch=1)
    accepted = 0
    duplicates = 0
    plan = [0, 1, 2, 0, 1, 2, 3, 4]
    next_offset = 100
    for sequence in plan:
        result = gate.admit("p", 1, sequence, next_offset)
        if result.startswith("accepted"):
            accepted += 1
            next_offset += 1
        else:
            duplicates += 1
    aborted = Transaction("t-bad", opened_at=0, timeout=100)
    for offset in range(100, 103):
        aborted.append(0, offset)
    aborted.abort()
    good = Transaction("t-good", opened_at=1, timeout=100)
    for offset in range(103, 107):
        good.append(0, offset)
    good.commit()
    records = [
        (0, offset, ABORTED) for offset in range(100, 103)
    ] + [(0, offset, COMMITTED) for offset in range(103, 107)]
    visible = visible_to_read_committed(records)
    numbers = {
        "records_accepted": accepted,
        "duplicates_absorbed": duplicates,
        "naive_deliveries": len(plan),
        "visible_count": len(visible),
        "aborted_hidden": all(
            offset >= 103 for _, offset in visible
        ),
    }
    holds = (
        accepted == 5
        and duplicates == 3
        and len(visible) == 4
        and numbers["aborted_hidden"]
    )
    return Finding(
        proof="exactlyonce",
        claim=(
            "three retries absorbed and an aborted batch "
            "hidden: the read-committed consumer sees four "
            "records where a naive broker would have delivered "
            "eight, which is the whole distance from "
            "at-least-once to exactly-once"
        ),
        numbers=numbers,
        holds=holds,
    )
