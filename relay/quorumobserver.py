"""Quorum observer: replicate the metadata without a vote or a say in commit.

The metadata quorum has voters, whose majority elects a leader and
whose acknowledgement commits a record, but it can also have
observers, brokers that replicate the metadata log without being
voters. An observer serves two purposes. It scales reads, because a
broker that needs the current metadata can catch it from an
observer instead of the small voter set, and it is a warm spare,
because an observer already holding the full log can be promoted to
voter faster than a fresh broker that must replicate from nothing.
The rule that keeps the quorum's guarantees intact is that an
observer does not count: it is not in the majority that elects, so
adding observers never changes how many acknowledgements a commit
needs, and it does not vote, so a partitioned observer cannot help
elect a leader on the wrong side of a split. This is the whole
point of the distinction, because if observers counted toward the
majority, adding read capacity would quietly change the
availability math, requiring more acknowledgements to commit and
making the quorum slower and more fragile as it grew. The registry
refuses to count observers in the commit majority and refuses to
promote an observer that has not caught up to within a small lag of
the leader, because promoting a lagging observer to voter would add
a voter that cannot yet acknowledge recent records, briefly
weakening the very majority the promotion was meant to strengthen.
The report separates voters from observers, because an operator
sizing the quorum for availability counts voters and one sizing it
for read capacity counts observers, and conflating them mis-sizes
both.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class QuorumMembership:
    leader_offset: int
    max_promote_lag: int
    voters: set[str] = field(default_factory=set)
    observers: dict[str, int] = field(default_factory=dict)

    def commit_majority(self) -> int:
        return len(self.voters) // 2 + 1

    def add_observer(self, broker: str, offset: int) -> None:
        if broker in self.voters:
            raise Invalid(f"{broker} is already a voter, not an observer")
        self.observers[broker] = offset

    def promote(self, broker: str) -> str:
        if broker not in self.observers:
            raise Invalid(f"{broker} is not an observer to promote")
        lag = self.leader_offset - self.observers[broker]
        if lag > self.max_promote_lag:
            raise Invalid(
                f"{broker} lags the leader by {lag}, past the "
                f"promote limit {self.max_promote_lag}; promoting it "
                "would add a voter that cannot acknowledge recent "
                "records, weakening the majority"
            )
        del self.observers[broker]
        self.voters.add(broker)
        return f"promoted {broker} to voter; commit majority now {self.commit_majority()}"

    def report(self) -> str:
        return (
            f"{len(self.voters)} voter(s) needing {self.commit_majority()} "
            f"to commit, {len(self.observers)} observer(s) for read "
            "capacity that never change the commit math"
        )
