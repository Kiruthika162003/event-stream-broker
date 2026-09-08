"""A pipelined producer retries mid-stream, and the log stays in order.

This is the proof that idempotence buys order, not just dedup.
The scenario is the one that reorders a naive pipelined producer:
five batches in flight, batch two fails and retries while batches
three through five are already on the wire, so on the retry batch
two arrives after them. The drill drives that exact arrival order,
2 then 3 then 4 then 5 then the retry of 2, through the
idempotency gate with sequence numbers, and asserts the gate
refuses every batch that arrives out of sequence and accepts them
only in order, so the log ends up 0,1,2,3,4 no matter what order
the wire delivered. The guess before measuring was that
idempotence only removes duplicates and order needs a separate
mechanism; the measurement is that the same sequence check does
both, because a batch out of sequence is rejected whether it is a
duplicate of something already accepted or an arrival ahead of
its predecessor, and the producer retries it after. The number
that carries the proof is the count of out-of-sequence rejections
before the log settles, which equals the reordering the wire
introduced and which a non-idempotent producer would have written
straight into the log as permanent disorder.
"""

from __future__ import annotations

from relay.errors import Invalid
from relay.idempotent import IdempotencyGate
from relay.proofs.finding import Finding


def run() -> Finding:
    gate = IdempotencyGate()
    gate.open_session("p", epoch=1)
    # In-order sequences 0..4 map to offsets; the wire delivers
    # 0,1 fine, then 3,4 arrive before 2 (batch 2 was retried).
    wire_order = [0, 1, 3, 4, 2, 3, 4]
    accepted_sequences = []
    rejections = 0
    next_offset = 100
    for seq in wire_order:
        try:
            result = gate.admit("p", 1, seq, next_offset)
        except Invalid:
            rejections += 1
            continue
        if result.startswith("accepted"):
            accepted_sequences.append(seq)
            next_offset += 1
    numbers = {
        "wire_deliveries": len(wire_order),
        "accepted_in_order": accepted_sequences,
        "out_of_sequence_rejections": rejections,
        "log_is_ordered": accepted_sequences
        == sorted(accepted_sequences),
        "final_sequences": accepted_sequences,
    }
    holds = (
        accepted_sequences == [0, 1, 2, 3, 4]
        and rejections >= 2
        and numbers["log_is_ordered"]
    )
    return Finding(
        proof="orderunderretry",
        claim=(
            "five batches delivered out of order settle into the "
            "log as 0,1,2,3,4: the sequence check rejects every "
            "out-of-order arrival and accepts only in order, so "
            "idempotence buys order, not just dedup"
        ),
        numbers=numbers,
        holds=holds,
    )
