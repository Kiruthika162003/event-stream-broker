"""Weighted assign: an equal split wastes a big consumer and floods a small one.

The default assignment gives every consumer in a group the same
number of partitions, which is right when the consumers are
identical, but a group is often mixed: some members run on larger
machines, some are warm and some just started, and an equal split
either leaves the big ones idle or buries the small ones. Weighted
assignment gives each consumer a share of the partitions
proportional to its declared weight, so a consumer with twice the
weight gets roughly twice the partitions, matching load to
capacity. The arithmetic has to handle the remainder honestly:
proportional shares rarely divide evenly, so the floor of each
consumer's ideal share is assigned first and the leftover
partitions go to the consumers with the largest fractional
remainders, the largest-remainder method, which keeps the total
exact and the overshoot at most one partition per consumer. Every
partition must be assigned to exactly one consumer, so the
assigner refuses to finish with partitions left over or with a
partition given twice, because an unassigned partition is a
partition no one consumes and a doubly-assigned one is processed
twice. The assigner refuses a consumer with zero or negative
weight, because a consumer that declared no capacity would be
assigned no partitions and sit in the group doing nothing while
counting against its size. The report states the spread between the
most- and least-loaded consumer, because the point of weighting is
a smaller spread in load than in partition count, and a weighting
that still leaves one consumer swamped has not helped.
"""

from __future__ import annotations

from relay.errors import Invalid


def assign(partitions: int, weights: dict[str, float]) -> dict[str, int]:
    if partitions < 0:
        raise Invalid("partition count cannot be negative")
    if not weights or any(w <= 0 for w in weights.values()):
        raise Invalid(
            "every consumer needs a positive weight; a zero-weight "
            "member would sit idle while counting against the group"
        )
    total = sum(weights.values())
    ideal = {c: partitions * w / total for c, w in weights.items()}
    base = {c: int(v) for c, v in ideal.items()}
    assigned = sum(base.values())
    leftover = partitions - assigned
    remainders = sorted(
        weights, key=lambda c: ideal[c] - base[c], reverse=True
    )
    for c in remainders[:leftover]:
        base[c] += 1
    if sum(base.values()) != partitions:
        raise Invalid("assignment did not cover every partition exactly once")
    return base


def spread(partitions: int, weights: dict[str, float]) -> str:
    result = assign(partitions, weights)
    per_weight = {
        c: result[c] / weights[c] for c in weights
    }
    hi = max(per_weight.values())
    lo = min(per_weight.values())
    return (
        f"assigned {result}; load-per-weight spread {hi - lo:.2f}, "
        "smaller than the partition-count spread because weighting "
        "matches partitions to capacity"
    )
