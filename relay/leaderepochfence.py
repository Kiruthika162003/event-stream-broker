"""Leader epoch fence: the request carries an epoch, and a mismatch means stale.

Leadership moves, and for a window after it moves the two sides of
a request can disagree about who leads a partition: a client with
stale metadata still thinks the old broker leads, or a broker that
has not yet learned it lost leadership still thinks it does. A
request that acts on the wrong belief is a correctness hazard, a
produce to a broker that is no longer leader would write to a log
that is now a follower's. The leader epoch fences it: the client
puts the leader epoch it believes current in the request, the
broker compares it to its own, and a mismatch tells which side is
stale. If the request's epoch is older than the broker's, the
client's metadata is stale, it is talking to a broker that used to
lead an earlier epoch, so the broker rejects with a fenced error
and the client refreshes metadata and retries against the real
leader. If the request's epoch is newer than the broker's, the
broker itself is stale, it has not yet processed the leadership
change the client already knows about, so it rejects and steps back
rather than serving as a leader it may no longer be. Only an exact
epoch match is served, because only then do both sides agree on the
current leadership. The fencer compares the request epoch to the
broker's current, serves on a match, and rejects a mismatch naming
which side is stale, because the remedy differs, the client
refreshes on an old epoch while the broker awaits its own metadata
update on a new one. It refuses a negative epoch, which no valid
leadership carries, and reports the direction of a mismatch,
because a broker seeing many newer-epoch requests is one lagging
the controller's leadership changes, a metadata propagation problem
distinct from clients simply holding stale caches."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Fenced, Invalid


@dataclass
class LeaderEpochFence:
    broker_epoch: int

    def __post_init__(self) -> None:
        if self.broker_epoch < 0:
            raise Invalid("a leader epoch cannot be negative")

    def check(self, request_epoch: int) -> str:
        if request_epoch < 0:
            raise Invalid("the request carries no valid leader epoch")
        if request_epoch < self.broker_epoch:
            raise Fenced(
                f"request epoch {request_epoch} < broker {self.broker_epoch}; "
                "the client's metadata is stale, it must refresh and retry "
                "against the real leader"
            )
        if request_epoch > self.broker_epoch:
            raise Fenced(
                f"request epoch {request_epoch} > broker {self.broker_epoch}; "
                "this broker is stale, it has not learned the leadership "
                "change and steps back"
            )
        return f"epoch {request_epoch} matches; served by the current leader"

    def mismatch_direction(self, request_epoch: int) -> str:
        if request_epoch == self.broker_epoch:
            return "match; both sides agree on leadership"
        if request_epoch > self.broker_epoch:
            return (
                "broker behind; many such requests mean it lags the "
                "controller's leadership changes, a propagation problem"
            )
        return "client behind; a stale metadata cache, refreshed on the fence"
