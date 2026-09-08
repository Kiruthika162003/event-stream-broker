"""Read index: a leader serves a linearizable read only after proving it still leads.

A read that must be linearizable, reflecting every write acked
before it, cannot just be answered by the leader from its local
state, because the leader might have been deposed without knowing
it: a network partition could have elected a new leader that took
writes this stale leader never saw, so its local state is behind.
The read index protocol makes the read safe without writing it
through the log. The leader records its current commit index as the
read index, then confirms it is still the leader by exchanging
heartbeats with a majority of followers, which proves no other
leader could have committed anything this one does not know about,
because a new leader would need that same majority. Once confirmed,
the leader waits until its state machine has applied entries up to
the read index, and then serves the read from local state, now
guaranteed to reflect all writes committed as of the read index. A
stale leader that lost its majority cannot get the heartbeat
confirmation, so it cannot serve the read and steps down, which is
exactly right: a leader that cannot prove it still leads must not
answer as if it does. This avoids the cost of a log write per read
while keeping linearizability, the reason it beats reading through
consensus for read-heavy workloads. The protocol records the read
index, confirms the quorum, waits for the apply to catch up, and
refuses to serve before both the quorum is confirmed and the state
machine has applied to the read index. It reports whether a read is
servable or the leader is stale, because a leader repeatedly unable
to confirm quorum is one that has lost contact with its followers,
a partition it should detect and step down from rather than block
reads on."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class ReadIndex:
    commit_index: int
    voters: int
    applied_index: int = 0
    confirmations: int = 0
    read_index: int = -1

    def __post_init__(self) -> None:
        if self.voters < 1:
            raise Invalid("need at least one voter")

    def majority(self) -> int:
        return self.voters // 2 + 1

    def begin_read(self) -> int:
        self.read_index = self.commit_index
        self.confirmations = 1  # the leader counts itself
        return self.read_index

    def confirm(self) -> None:
        self.confirmations += 1

    def quorum_confirmed(self) -> bool:
        return self.confirmations >= self.majority()

    def apply_to(self, index: int) -> None:
        self.applied_index = max(self.applied_index, index)

    def serve(self) -> str:
        if self.read_index < 0:
            raise Invalid("begin the read to set its read index first")
        if not self.quorum_confirmed():
            raise Invalid(
                f"only {self.confirmations}/{self.voters} confirmed, below "
                f"majority {self.majority()}; this leader cannot prove it still "
                "leads and must step down, not serve a possibly-stale read"
            )
        if self.applied_index < self.read_index:
            raise Invalid(
                f"state machine applied to {self.applied_index}, behind the "
                f"read index {self.read_index}; wait for it to catch up so the "
                "read reflects all committed writes"
            )
        return f"linearizable read served as of index {self.read_index}"
