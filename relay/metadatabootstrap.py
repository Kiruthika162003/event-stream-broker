"""Metadata bootstrap: any seed broker will do, because it only points onward.

A client starts knowing a list of bootstrap brokers, and a common
misunderstanding is that those brokers must be the ones it will
produce to or fetch from. They need not be: a bootstrap broker's
only job is to answer a metadata request, telling the client which
brokers lead which partitions, and once the client has that
metadata it connects directly to the actual leaders, which may be
brokers not in the bootstrap list at all. So the bootstrap list is a
way in, not a routing table, and it is enough for it to contain any
few reachable brokers of the cluster, because any broker can serve
metadata for the whole cluster. The client tries the bootstrap
brokers in order until one answers, tolerating that some are down,
because the point of listing several is that the client can start
as long as one is reachable. This is why a bootstrap list of one
broker is fragile, not wrong: it works until that one broker is
down at the moment a client starts, and then the client cannot
bootstrap even though the rest of the cluster is healthy. The
bootstrapper tries brokers in order, returns the metadata from the
first that answers, and refuses an empty bootstrap list, which
leaves the client no way in at all. It refuses to route to a leader
before metadata has been fetched, because the client does not know
the leaders yet, and it reports how many bootstrap brokers had to
be tried before one answered, because a client routinely falling
through to the last broker in its list is one whose earlier
bootstrap brokers are down, a fragility to fix before the last one
dies too.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class Bootstrapper:
    bootstrap: list[str]
    reachable: set[str] = field(default_factory=set)
    leaders: dict[int, str] = field(default_factory=dict)
    _fetched: bool = False

    def __post_init__(self) -> None:
        if not self.bootstrap:
            raise Invalid(
                "an empty bootstrap list leaves the client no way into "
                "the cluster"
            )

    def fetch_metadata(self) -> str:
        for i, broker in enumerate(self.bootstrap):
            if broker in self.reachable:
                self._fetched = True
                return (
                    f"bootstrapped from '{broker}' after trying {i + 1} "
                    "broker(s); metadata fetched, now routing to leaders"
                )
        raise Invalid(
            "no bootstrap broker was reachable; the client cannot start "
            "even if the rest of the cluster is healthy"
        )

    def leader_of(self, partition: int) -> str:
        if not self._fetched:
            raise Invalid(
                "cannot route to a leader before metadata is fetched; the "
                "client does not know the leaders yet"
            )
        if partition not in self.leaders:
            raise Invalid(f"no leader known for partition {partition}")
        return self.leaders[partition]

    def tries_needed(self) -> str:
        for i, broker in enumerate(self.bootstrap):
            if broker in self.reachable:
                fell_through = i
                break
        else:
            return "no bootstrap broker reachable"
        if fell_through == 0:
            return "first bootstrap broker answered; healthy"
        return (
            f"fell through {fell_through} down broker(s) before one "
            "answered; the earlier bootstrap brokers are down, a fragility"
        )
