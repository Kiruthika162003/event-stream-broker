"""Replica selector: let a consumer fetch from a nearby follower, not the leader.

By default every consumer fetches from the partition leader, which is
correct but can be expensive: if the leader is in another rack or
another availability zone, every fetched byte crosses that boundary
and is billed and delayed for the crossing. Follower fetching lets a
consumer read from an in-sync replica in its own rack instead, so the
bytes stay local, cutting cross-zone traffic for read-heavy fanout.
The selector chooses, for a consumer's rack, an in-sync replica in
that same rack, preferring the one whose log end is highest so the
consumer reads the freshest local copy. When no in-sync replica shares
the consumer's rack, it falls back to the leader, because a distant
in-sync read is still better than reading from a replica that is not
in sync, which could serve records that later get truncated. Two
constraints keep the read correct. Only in-sync replicas are eligible,
because a follower that has fallen out of sync may be behind the high
watermark and could expose records that are not yet committed. And a
follower serves reads only up to the high watermark it has learned,
never past it, so a consumer fetching from a follower sees exactly the
committed prefix, the same visibility the leader would give, just
possibly a moment stale. The selector returns the chosen replica and
whether it was a local hit or a leader fallback, refuses to select
when no replica is in sync at all, and reports the staleness of a
chosen follower, its log end below the leader's, because a follower
that lags far behind turns a bandwidth saving into a latency cost the
consumer did not ask for."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class _Replica:
    broker: str
    rack: str
    log_end: int
    in_sync: bool


@dataclass
class ReplicaSelector:
    leader: str
    replicas: dict[str, _Replica] = field(default_factory=dict)

    def add_replica(
        self, broker: str, rack: str, log_end: int, *, in_sync: bool
    ) -> None:
        self.replicas[broker] = _Replica(
            broker=broker, rack=rack, log_end=log_end, in_sync=in_sync
        )

    def select(self, consumer_rack: str) -> tuple[str, str]:
        if not any(r.in_sync for r in self.replicas.values()):
            raise Invalid(
                "no replica is in sync; there is nothing safe to read from, a "
                "not-in-sync replica could expose uncommitted records"
            )
        local = [
            r
            for r in self.replicas.values()
            if r.in_sync and r.rack == consumer_rack
        ]
        if local:
            best = max(local, key=lambda r: r.log_end)
            return best.broker, "local hit"
        return self.leader, "leader fallback"

    def staleness(self, broker: str) -> int:
        if broker not in self.replicas:
            raise Invalid(f"'{broker}' is not a known replica")
        leader_end = self.replicas[self.leader].log_end
        return max(0, leader_end - self.replicas[broker].log_end)

    def note(self, consumer_rack: str) -> str:
        broker, how = self.select(consumer_rack)
        lag = self.staleness(broker)
        return (
            f"consumer in '{consumer_rack}' reads from '{broker}' ({how}), "
            f"{lag} record(s) behind the leader; a far-behind follower turns a "
            "bandwidth saving into a latency cost"
        )
