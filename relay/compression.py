"""Compression: batch-level codecs, chosen by the workload, not by fashion.

A producer can compress a batch before sending, and the codec
choice trades compression ratio against CPU, but the decision is
usually made by copying whatever another team uses, which is how a
CPU-bound producer ends up running the slowest codec for a
marginal ratio gain it cannot afford. The selector reasons from
the workload. A producer that is network-bound, shipping across
regions where bandwidth is the scarce resource, should spend CPU
for ratio, the high-ratio codec pays for its cost in reduced
bytes on an expensive link. A producer that is CPU-bound, already
saturating cores, should use a fast codec or none, because a
better ratio it computes by stealing cycles from its actual work
is a false economy. The selector also captures the property that
compression is per-batch, so it interacts with batching: a codec
compresses a full batch far better than the same records sent
singly, because compression finds redundancy across records, so a
producer with poor batching gets poor compression regardless of
codec, and the fix is linger, not a fancier codec. The report
states the binding resource and the recommended codec together,
because a codec recommendation without the resource that drove it
is advice that stops making sense the moment the workload shifts,
and it flags the specific mistake of high-ratio compression on
tiny batches, which pays full CPU for almost no ratio because
there is too little data to find redundancy in.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

CODECS = {
    "none": (1.0, 0),
    "fast": (2.0, 1),
    "balanced": (3.0, 3),
    "high": (4.0, 8),
}


@dataclass(frozen=True)
class Workload:
    binding_resource: str
    avg_batch_records: int

    def __post_init__(self) -> None:
        if self.binding_resource not in ("network", "cpu"):
            raise Invalid(
                "the binding resource is network or cpu"
            )
        if self.avg_batch_records < 1:
            raise Invalid("batch size must be positive")


def recommend_codec(workload: Workload) -> str:
    if workload.avg_batch_records < 4:
        return (
            "fix batching first: high-ratio compression on tiny "
            "batches pays full CPU for almost no ratio, too "
            "little data to find redundancy; raise linger, not "
            "the codec"
        )
    if workload.binding_resource == "network":
        return (
            "codec high: network-bound, so spend CPU for ratio "
            "and pay it back in bytes on an expensive link"
        )
    return (
        "codec fast: cpu-bound, so a ratio computed by stealing "
        "cycles from real work is a false economy"
    )


def effective_ratio(codec: str, batch_records: int) -> float:
    if codec not in CODECS:
        raise Invalid(f"unknown codec {codec}")
    nominal, _ = CODECS[codec]
    if batch_records < 4:
        # small batches realize only a fraction of the ratio
        return 1.0 + (nominal - 1.0) * (batch_records / 4)
    return nominal


def cpu_cost(codec: str) -> int:
    if codec not in CODECS:
        raise Invalid(f"unknown codec {codec}")
    return CODECS[codec][1]
