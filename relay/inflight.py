"""In-flight requests: pipelining is fast, but retries can reorder it.

A producer pipelines by sending several batches before the first
is acknowledged, which fills the network and lifts throughput.
The trap is retries. If batches one and two are in flight, batch
one fails and is retried, and batch two already succeeded, then
batch one's records land after batch two's, and the per-partition
order the producer promised is broken, silently, only under the
failure that triggers the retry, which is why it survives testing
and appears in production. There are exactly two safe
configurations and the checker names them: pipelining with at
most one in-flight request per partition, which preserves order
by never having a second batch to leapfrog, or pipelining freely
with idempotence enabled, where the broker's sequence numbers let
it reject an out-of-order retry and preserve order without
capping throughput. What is unsafe is the middle a lot of
producers sit in by default: many in-flight without idempotence,
which is fast and correct until the first retry and wrong
forever after. The checker refuses that combination with the
two safe alternatives, because a silent ordering bug is the
worst kind, indistinguishable from working until it is not.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class ProducerPipeline:
    max_in_flight: int
    idempotent: bool

    def __post_init__(self) -> None:
        if self.max_in_flight < 1:
            raise Invalid("at least one request must be in flight")


def ordering_safe(pipeline: ProducerPipeline) -> bool:
    return pipeline.max_in_flight == 1 or pipeline.idempotent


def check_ordering(pipeline: ProducerPipeline) -> str:
    if pipeline.max_in_flight == 1:
        return (
            "order preserved: one in-flight request means no "
            "second batch can leapfrog a retried first"
        )
    if pipeline.idempotent:
        return (
            f"order preserved: {pipeline.max_in_flight} in-flight "
            "with idempotence, where sequence numbers reject an "
            "out-of-order retry without capping throughput"
        )
    raise Invalid(
        f"UNSAFE: {pipeline.max_in_flight} in-flight without "
        "idempotence reorders on the first retry, silently and "
        "forever; either cap in-flight to 1 or enable "
        "idempotence, because a silent ordering bug is "
        "indistinguishable from working until it is not"
    )


def throughput_class(pipeline: ProducerPipeline) -> str:
    if not ordering_safe(pipeline):
        raise Invalid("an unsafe pipeline has no throughput to rate")
    if pipeline.max_in_flight == 1 and not pipeline.idempotent:
        return "safe but throttled: one batch at a time"
    return (
        f"safe and pipelined: {pipeline.max_in_flight} in-flight, "
        "order held by sequence numbers"
    )
