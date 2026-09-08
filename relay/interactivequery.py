"""Interactive query: read a stream's live state, from the instance that owns it.

A stream application's state, the running aggregates in its state
stores, is often worth querying directly rather than writing out to
a database, and interactive queries do that: a request for a key's
current value is answered from the local state store of a running
instance. The catch is that the state is partitioned across
instances the same way the input is, so a key's value lives on
exactly one instance, the one whose task owns that key's partition,
and a query must reach that instance. The router computes the key's
partition with the same hash the stream used to place it, maps the
partition to the instance that owns it, and directs the query
there, so a query arriving at the wrong instance is redirected
rather than answered from a store that does not have the key. This
is the piece that makes a distributed state store queryable as if
it were one store: the caller asks any instance, and the routing
finds the owner. Availability during a rebalance or an instance
failure is the wrinkle: while the active owner is down, its
partition's state is unavailable until another instance takes over
and restores it, unless a standby replica of that state exists, in
which case the query can be served from the standby with the
caveat that the standby may be slightly behind, a stale read the
caller must be willing to accept. The router places a key, resolves
the owning instance, redirects a misrouted query, and can fall back
to a standby when the active is down, naming the staleness. It
refuses to route a partition with no owner, an unavailable state the
caller must retry, and reports which instance owns a key, because a
query latency spike is often every query routing to one overloaded
instance that owns a hot key's partition."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class QueryRouter:
    partitions: int
    owners: dict[int, str] = field(default_factory=dict)
    standbys: dict[int, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.partitions < 1:
            raise Invalid("need at least one partition")

    def partition_for(self, key: str) -> int:
        return (hash(key) & 0x7FFFFFFF) % self.partitions

    def owner_of(self, key: str) -> str:
        part = self.partition_for(key)
        owner = self.owners.get(part)
        if owner is None:
            raise Invalid(
                f"partition {part} for key '{key}' has no owner; its state is "
                "unavailable, the caller must retry after a takeover"
            )
        return owner

    def route(self, key: str, arrived_at: str) -> str:
        owner = self.owner_of(key)
        if arrived_at == owner:
            return f"served '{key}' locally at '{owner}'"
        return f"redirect '{key}' from '{arrived_at}' to its owner '{owner}'"

    def route_with_fallback(self, key: str) -> str:
        part = self.partition_for(key)
        if part in self.owners:
            return f"served by active owner '{self.owners[part]}'"
        standby = self.standbys.get(part)
        if standby is None:
            raise Invalid(f"partition {part} has no active or standby; unavailable")
        return (
            f"active down; served by standby '{standby}' with a stale-read "
            "caveat, it may be slightly behind"
        )
