"""Metadata cache: fast routing, refreshed on the error that proves it stale.

A client caches cluster metadata, which partitions exist and
which broker leads each, so it can route a produce or fetch
without asking the controller every time. The cache is what makes
the client fast and what makes it occasionally wrong, because
leadership moves and the cache does not know until it tries. The
refresh strategy that works is not a timer: a periodic refresh is
either too frequent, wasting requests, or too slow, routing to
dead leaders for the length of the interval. The right trigger is
the error itself. When the client routes to a broker that is no
longer the leader, the broker returns not-leader, and that error
is the signal to refresh, so the cache is corrected exactly when
and only when it is proven wrong, self-healing on the failure
rather than polling against it. The cache also refreshes
proactively on one specific event, a metadata version in a
response higher than the cached one, because a response carrying
a newer version is the broker telling the client its view moved,
and ignoring that hint means routing wrong until the next error.
The report counts refreshes triggered by error against refreshes
that were proactive, since a cache refreshing mostly on errors is
a cache that is mostly wrong before it corrects, which points at
a cluster churning leadership faster than a healthy one should.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class MetadataCache:
    version: int = 0
    leaders: dict[int, str] = field(default_factory=dict)
    refreshes_on_error: int = 0
    refreshes_proactive: int = 0

    def install(self, version: int, leaders: dict[int, str]) -> None:
        if version < self.version:
            raise Invalid(
                "cannot install an older metadata version over "
                "a newer one; that would route backward in time"
            )
        self.version = version
        self.leaders = dict(leaders)

    def leader_of(self, partition: int) -> str:
        leader = self.leaders.get(partition)
        if leader is None:
            raise Invalid(
                f"partition {partition} not in the cache; "
                "refresh metadata"
            )
        return leader

    def on_not_leader(
        self, partition: int, new_version: int, new_leader: str
    ) -> str:
        self.refreshes_on_error += 1
        self.install(
            new_version,
            {**self.leaders, partition: new_leader},
        )
        return (
            f"refreshed on not-leader error: partition "
            f"{partition} now on {new_leader}; corrected exactly "
            "when proven wrong"
        )

    def on_newer_version_seen(
        self, seen_version: int, refreshed_leaders: dict[int, str]
    ) -> str:
        if seen_version <= self.version:
            return "no refresh: the seen version is not newer"
        self.refreshes_proactive += 1
        self.install(seen_version, refreshed_leaders)
        return (
            f"refreshed proactively to version {seen_version}; a "
            "response with a newer version is the broker saying "
            "the view moved"
        )

    def health(self) -> str:
        total = self.refreshes_on_error + self.refreshes_proactive
        if total == 0:
            return "no refreshes; the cache has been stable"
        error_share = self.refreshes_on_error / total
        note = (
            "; mostly on errors means the cache is mostly wrong "
            "before it corrects, a cluster churning leadership"
            if error_share > 0.5
            else ""
        )
        return (
            f"{self.refreshes_on_error} error refresh(es), "
            f"{self.refreshes_proactive} proactive{note}"
        )
