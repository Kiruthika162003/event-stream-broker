"""Replication: the watermark advances at the pace of the slowest promise.

A partition has a leader and followers, and the high watermark
is not the leader's choice; it is the arithmetic of the
in-sync set. Each replica reports the offset it has durably
fetched, and the committed offset is the minimum across the
in-sync replicas, because a record is a promise only when every
replica the broker vowed to keep in sync actually holds it.
Followers that fall too far behind are removed from the in-sync
set so one slow disk cannot freeze the watermark for everyone,
but shrinking the set is the dangerous move: a set of one is a
single point of failure wearing a replication badge, so the
minimum-in-sync floor refuses to commit at all when the set
drops below it, choosing unavailability over the quiet
acknowledgement of writes that one crash would erase. The
report always states which replica is the pace-setter, because
"the watermark is stuck" is a symptom and "follower-3 is 400
behind" is a diagnosis.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class ReplicaState:
    name: str
    fetched_offset: int
    in_sync: bool = True


@dataclass
class ReplicationSet:
    leader: str
    followers: dict[str, ReplicaState]
    min_in_sync: int
    max_lag: int
    leader_end_offset: int = 0

    def __post_init__(self) -> None:
        if self.min_in_sync < 1:
            raise Invalid("min in-sync must be at least one")

    def _in_sync_offsets(self) -> list[int]:
        offsets = [self.leader_end_offset]
        for state in self.followers.values():
            if state.in_sync:
                offsets.append(state.fetched_offset)
        return offsets

    def in_sync_count(self) -> int:
        return 1 + sum(
            1 for s in self.followers.values() if s.in_sync
        )

    def evict_laggards(self) -> list[str]:
        evicted = []
        for state in self.followers.values():
            if (
                state.in_sync
                and self.leader_end_offset - state.fetched_offset
                > self.max_lag
            ):
                state.in_sync = False
                evicted.append(state.name)
        return evicted

    def committable_watermark(self) -> int:
        if self.in_sync_count() < self.min_in_sync:
            raise Invalid(
                f"in-sync set is {self.in_sync_count()}, below "
                f"the floor of {self.min_in_sync}; the broker "
                "chooses unavailability over acknowledging "
                "writes one crash would erase"
            )
        return min(self._in_sync_offsets())

    def pace_report(self) -> str:
        slowest_name = self.leader
        slowest_offset = self.leader_end_offset
        for state in self.followers.values():
            if (
                state.in_sync
                and state.fetched_offset < slowest_offset
            ):
                slowest_offset = state.fetched_offset
                slowest_name = state.name
        lag = self.leader_end_offset - slowest_offset
        return (
            f"in-sync {self.in_sync_count()}, pace-setter "
            f"{slowest_name} at {slowest_offset} ({lag} behind "
            "the leader)"
        )
