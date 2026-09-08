"""Fetch from follower: read from the near replica, but never past its truth.

By default a consumer reads from the leader, which is correct
and, across cloud zones, expensive: a consumer in zone B reading
a leader in zone A pays cross-zone network on every fetch, and
that bill can dwarf the compute. Fetch-from-follower lets the
consumer read from a replica in its own zone, cutting the cost,
but the follower trails the leader, so its own high watermark is
below the leader's, and the rule that keeps this safe is that a
follower serves reads only up to its own high watermark, never
the leader's. A consumer reading a near follower sees slightly
older committed data, which is a latency-for-cost trade it opted
into, not a correctness loss, because every record it reads is
still committed, just committed a moment ago. The selector picks
the nearest in-sync replica and states the staleness in offsets,
because a consumer that thinks it is current on a follower
trailing by a thousand records is making decisions on stale data
without knowing it, and staleness a reader knows about is a
trade while staleness it does not is a bug.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid, Missing


@dataclass(frozen=True)
class ReplicaEndpoint:
    broker: str
    rack: str
    high_watermark: int
    in_sync: bool


def select_replica(
    consumer_rack: str,
    leader: ReplicaEndpoint,
    followers: list[ReplicaEndpoint],
) -> tuple[ReplicaEndpoint, str]:
    same_rack = [
        f
        for f in followers
        if f.rack == consumer_rack and f.in_sync
    ]
    if not same_rack:
        return leader, (
            f"no in-sync replica in rack {consumer_rack}; "
            "reading the leader, paying cross-zone to stay "
            "current"
        )
    nearest = max(
        same_rack, key=lambda f: f.high_watermark
    )
    staleness = leader.high_watermark - nearest.high_watermark
    return nearest, (
        f"reading {nearest.broker} in rack {consumer_rack}, "
        f"trailing the leader by {staleness} record(s); a trade "
        "you opted into, and stated so it stays a trade"
    )


def safe_read_ceiling(replica: ReplicaEndpoint) -> int:
    return replica.high_watermark


def validate_follower_read(
    replica: ReplicaEndpoint, offset: int
) -> None:
    if offset >= replica.high_watermark:
        raise Missing(
            f"offset {offset} is above this follower's "
            f"watermark {replica.high_watermark}; a follower "
            "serves only its own committed truth, never the "
            "leader's"
        )
    if not replica.in_sync:
        raise Invalid(
            f"{replica.broker} is out of sync and must not "
            "serve reads; its data may be about to truncate"
        )
