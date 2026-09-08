"""Min in-sync replicas: refuse an acks=all write the ISR is too thin to keep.

Acks=all promises a producer that a record is committed only once
every in-sync replica has it, which sounds like strong durability
until the in-sync set shrinks. If replicas fall out of sync until only
the leader remains, acks=all still returns success, because the leader
is the whole in-sync set and it has the record, and then the leader
fails and the record is gone despite the acknowledgment. Min in-sync
replicas closes that hole. It is a floor on how many replicas must be
in sync for an acks=all write to be accepted at all. With the floor at
two, a write is accepted only while at least two replicas are in sync,
so an acknowledged record lives on at least two brokers and survives
any single failure. When the in-sync set drops below the floor, the
leader stops accepting acks=all writes and returns a not-enough-
replicas error, which is the honest signal: the partition would rather
reject the write than accept it under a promise it can no longer keep.
This is a deliberate availability-for-durability trade, the mirror of
unclean election, and it only governs acks=all, because a producer
asking for weaker acks has already accepted weaker durability. The
enforcer holds the floor and the current in-sync count, admits an
acks=all write only when the count meets the floor, always admits a
weaker-acks write, and refuses a floor above the replication factor,
because a floor no in-sync set could ever reach would make the
partition permanently unwritable. It reports the margin, the in-sync
count above the floor, because a partition sitting exactly at the
floor is one replica away from rejecting writes, the moment to look
before the producers start seeing errors."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class MinInSyncReplicas:
    floor: int
    replication_factor: int

    def __post_init__(self) -> None:
        if self.floor < 1:
            raise Invalid("the floor must be at least one")
        if self.floor > self.replication_factor:
            raise Invalid(
                f"floor {self.floor} exceeds the replication factor "
                f"{self.replication_factor}; no in-sync set could ever reach "
                "it, the partition would be permanently unwritable"
            )

    def admit(self, in_sync_count: int, acks: str) -> str:
        if acks != "all":
            # weaker acks already accepted weaker durability; the floor is moot
            return f"admitted (acks={acks} does not require the floor)"
        if in_sync_count < self.floor:
            raise Invalid(
                f"only {in_sync_count} replica(s) in sync, floor is {self.floor}; "
                "not-enough-replicas, the partition rejects the write rather "
                "than accept it under a promise it cannot keep"
            )
        return f"admitted (acks=all, {in_sync_count} in sync meets floor {self.floor})"

    def margin(self, in_sync_count: int) -> int:
        return in_sync_count - self.floor

    def note(self, in_sync_count: int) -> str:
        margin = self.margin(in_sync_count)
        edge = " (at the floor, one replica from rejecting writes)" if margin == 0 else ""
        return (
            f"{in_sync_count} in sync, floor {self.floor}, margin {margin}{edge}; "
            "a partition at the floor is the moment to look before producers "
            "see errors"
        )
