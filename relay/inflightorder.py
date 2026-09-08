"""In-flight ordering: pipelining is fast, and without care it reorders.

A producer can have multiple batches in flight to a partition at
once, which pipelines and raises throughput, but it opens a
reordering hole that surprises everyone the first time. If batch
one and batch two are both in flight and batch one fails and
retries while batch two succeeds, batch two's records land before
batch one's on the retry, and the partition's order, the thing it
exists to preserve, is silently broken. The naive fix is to allow
only one in-flight batch, which restores order at the cost of the
pipelining that made the producer fast. The real fix is
idempotence: with sequence numbers on every batch, the broker
rejects a batch that arrives out of sequence, so batch two
arriving before batch one is refused and retried after, and order
is preserved even with several batches in flight. The interaction
is the rule the resolver enforces: multiple in-flight batches are
safe only with idempotence enabled, and a producer configured for
high in-flight without idempotence is a producer that will
reorder under retries, a correctness bug hiding behind a
performance setting. The resolver refuses that combination for a
producer that declared it needs ordering, because the setting
looks like pure throughput tuning and silently trades away the
guarantee, and it names the safe alternative: keep the
pipelining, turn on idempotence, and get both order and
throughput, which is the whole reason idempotent producers exist.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class ProducerConfig:
    max_in_flight: int
    idempotent: bool
    needs_ordering: bool

    def __post_init__(self) -> None:
        if self.max_in_flight < 1:
            raise Invalid("at least one in-flight batch is required")


def validate_ordering(config: ProducerConfig) -> str:
    if config.max_in_flight == 1:
        return (
            "one in-flight batch: order preserved by serialization, "
            "at the cost of the pipelining that raises throughput"
        )
    if config.idempotent:
        return (
            f"{config.max_in_flight} in-flight with idempotence: "
            "sequence numbers reject out-of-order batches, so "
            "pipelining and order both hold, the reason idempotent "
            "producers exist"
        )
    if config.needs_ordering:
        raise Invalid(
            f"{config.max_in_flight} in-flight without idempotence "
            "will reorder under retries; a correctness bug hiding "
            "behind a performance setting. Keep the pipelining, "
            "turn on idempotence, get both"
        )
    return (
        f"{config.max_in_flight} in-flight without idempotence: "
        "reordering possible under retries, accepted because this "
        "producer declared it does not need ordering"
    )


def would_reorder(
    config: ProducerConfig, batch_one_failed: bool
) -> bool:
    if config.idempotent or config.max_in_flight == 1:
        return False
    return batch_one_failed
