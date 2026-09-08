"""Offline partition: no leader means no reads and no writes, not a slow path.

A partition is offline when it has no leader, which happens when
every replica that could lead is unavailable: all replicas down, or
the only surviving replicas out of the in-sync set while unclean
election is disabled to protect committed data. An offline
partition is different in kind from an under-replicated one. Under-
replicated still has a leader and still serves, just with less
redundancy, so produce and fetch continue; offline has no leader
at all, so there is nowhere to send a produce and nothing to serve
a fetch, and the honest behavior is to reject both rather than
block a client forever waiting for a leader that is not coming. The
model tracks each replica's availability and whether it is in the
in-sync set, and decides leadership: a partition is online if some
in-sync replica is available, and offline otherwise, unless unclean
election is allowed, in which case an available out-of-sync replica
can lead at the known cost of losing the records it never
replicated. The model refuses to declare a partition online with a
leader that is not actually available, because routing produce to a
dead leader is the stall the offline state exists to make visible.
It names why a partition is offline, all-down versus in-sync-lost-
with-unclean-disabled, because the two have different fixes: the
first waits for a broker to return, the second is a policy choice
between availability and the committed data unclean election would
discard. The report states whether enabling unclean election would
bring the partition back and what it would cost, so the operator
decides with the tradeoff in front of them rather than flipping a
flag blind.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class Replica:
    broker: str
    available: bool
    in_sync: bool


@dataclass
class PartitionAvailability:
    replicas: list[Replica] = field(default_factory=list)
    allow_unclean: bool = False

    def _available_in_sync(self) -> list[Replica]:
        return [r for r in self.replicas if r.available and r.in_sync]

    def _available_any(self) -> list[Replica]:
        return [r for r in self.replicas if r.available]

    def is_online(self) -> bool:
        if self._available_in_sync():
            return True
        return self.allow_unclean and bool(self._available_any())

    def leader(self) -> str:
        if self._available_in_sync():
            return self._available_in_sync()[0].broker
        if self.allow_unclean and self._available_any():
            return self._available_any()[0].broker
        raise Invalid(
            "the partition is offline; refusing to name a leader "
            "that is not available, because routing produce to a "
            "dead leader is the stall this state makes visible"
        )

    def why_offline(self) -> str:
        if self.is_online():
            return "online"
        if not self._available_any():
            return (
                "offline: all replicas down; the fix is to wait for "
                "a broker to return"
            )
        return (
            "offline: in-sync replicas lost and unclean election "
            "disabled; the fix is a policy choice between "
            "availability and the committed data unclean would discard"
        )

    def unclean_recovery(self) -> str:
        if self.is_online():
            return "already online; no unclean election needed"
        candidates = self._available_any()
        if not candidates:
            return "no available replica; unclean election cannot help"
        return (
            f"enabling unclean election would let {candidates[0].broker} "
            "lead, restoring availability at the cost of records it "
            "never replicated"
        )
