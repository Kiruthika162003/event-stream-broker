"""Replica fetcher: a follower pulls from the leader, and its ask is its ack.

Replication in this broker is pull-based: a follower does not sit and
wait for the leader to push records, it runs a fetch loop that asks the
leader for records starting at the follower's current fetch offset,
appends what comes back to its own log, and advances the fetch offset
by what it received, then asks again from there. The elegant part is
that the fetch request itself is the acknowledgment. When a follower
asks for offset n, it is telling the leader it already has everything
below n, so the leader learns each follower's progress from the offset
it fetches from, with no separate ack message. The leader uses those
fetch offsets to advance the high watermark: the watermark moves up to
the lowest fetch offset across all in-sync followers, because that is
the highest offset every in-sync replica is known to hold. A follower
that stops fetching stops acking, its fetch offset stalls, and it is
eventually dropped from the in-sync set for falling behind, the same
signal serving double duty. The fetcher tracks the follower's fetch
offset and log end, performs a fetch that appends a run of records and
advances both, and reports the fetch offset that the leader reads as
the acknowledgment. It refuses a fetch from an offset past the leader's
log end, since there is nothing there to send, and refuses a negative
record count. It reports the follower's fetch offset against the
leader's log end, the replication lag in records, because a fetch
offset that stops advancing while the leader's log grows is a follower
falling out of sync, visible in exactly the number the leader watches."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class ReplicaFetcher:
    leader_log_end: int
    fetch_offset: int = 0

    def __post_init__(self) -> None:
        if self.fetch_offset < 0 or self.leader_log_end < 0:
            raise Invalid("offsets cannot be negative")

    def fetch(self, count: int) -> int:
        if count < 0:
            raise Invalid("cannot fetch a negative number of records")
        if self.fetch_offset > self.leader_log_end:
            raise Invalid(
                f"fetch offset {self.fetch_offset} is past the leader's log end "
                f"{self.leader_log_end}; there is nothing there to send"
            )
        available = self.leader_log_end - self.fetch_offset
        received = min(count, available)
        self.fetch_offset += received
        return received

    def acknowledged_through(self) -> int:
        # the fetch offset is the ack: everything below it the follower holds
        return self.fetch_offset

    def lag(self) -> int:
        return self.leader_log_end - self.fetch_offset

    def note(self) -> str:
        return (
            f"fetch offset {self.fetch_offset}, leader log end "
            f"{self.leader_log_end}, lag {self.lag()}; a fetch offset that stops "
            "advancing while the leader grows is a follower falling out of sync"
        )
