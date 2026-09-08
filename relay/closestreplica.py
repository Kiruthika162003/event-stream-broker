"""Closest replica: read from the nearest in-sync copy, distance measured honestly.

Fetch-from-follower picks a replica in the consumer's own rack,
but rack is a coarse proxy for what actually matters, network
distance, and a richer selection uses a measured distance metric:
same host is nearest, then same rack, then same datacenter, then
cross-region, each a step more expensive in latency and dollars.
The selector picks the closest in-sync replica by this metric,
falling back outward only when no nearer replica qualifies, so a
consumer reads from the cheapest source that can correctly serve
it. The correctness constraint from fetch-from-follower still
holds absolutely: distance never overrides in-sync, a nearby but
out-of-sync replica is not a candidate, because reading stale
data cheaply is not a bargain, it is a bug with a discount. The
selector is honest about the case where the only in-sync replica
is the farthest one: it selects it and reports the distance,
rather than silently serving a nearer out-of-sync copy, because
the whole point of the distance metric is to reduce cost within
correctness, never to trade correctness for cost. The report
names the distance tier chosen and what was skipped, because a
consumer reading cross-region when a same-rack replica exists but
is out of sync is paying for a replica's health problem, and that
cost is worth surfacing so someone fixes the sick replica rather
than paying its bill forever.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

DISTANCE = {
    "same-host": 0,
    "same-rack": 1,
    "same-datacenter": 2,
    "cross-region": 3,
}


@dataclass(frozen=True)
class ReplicaLocation:
    broker: str
    distance_tier: str
    in_sync: bool

    def __post_init__(self) -> None:
        if self.distance_tier not in DISTANCE:
            raise Invalid(
                f"unknown distance tier {self.distance_tier}"
            )

    def distance(self) -> int:
        return DISTANCE[self.distance_tier]


def select_closest(
    replicas: list[ReplicaLocation],
) -> tuple[ReplicaLocation, str]:
    in_sync = [r for r in replicas if r.in_sync]
    if not in_sync:
        raise Invalid(
            "no in-sync replica to read; distance never "
            "overrides correctness, and there is nothing correct "
            "to pick"
        )
    chosen = min(
        in_sync, key=lambda r: (r.distance(), r.broker)
    )
    skipped_nearer = [
        r
        for r in replicas
        if not r.in_sync and r.distance() < chosen.distance()
    ]
    if skipped_nearer:
        names = ", ".join(sorted(r.broker for r in skipped_nearer))
        return chosen, (
            f"reading {chosen.broker} at {chosen.distance_tier}; "
            f"nearer but out-of-sync ({names}) skipped, so this "
            "consumer pays for a replica's health problem, worth "
            "surfacing"
        )
    return chosen, (
        f"reading {chosen.broker} at {chosen.distance_tier}, the "
        "closest in-sync copy"
    )
