"""Rack awareness: spread a partition's replicas across racks, not within one.

Replication protects a partition against a broker failing, but only if
the replicas do not all fail together. Brokers in the same rack share a
power feed and a top-of-rack switch, so a rack outage takes down every
broker in it at once, and three replicas in one rack give the
durability of one. Rack-aware placement spreads a partition's replicas
across as many distinct racks as possible, so losing a whole rack
costs a partition at most the replicas that rack held, never all of
them. The placement walks the brokers in an order that alternates
racks, picking the next broker from a rack not yet used for this
partition before reusing any rack, so with at least as many racks as
the replication factor every replica lands in its own rack. When there
are fewer racks than replicas, some rack must hold two, and the
placement spreads the doubling as evenly as it can rather than piling
onto one rack, and it reports how many racks the replicas span so an
operator can see whether a single rack failure could drop the
partition below its minimum in-sync replicas. It refuses a replication
factor larger than the number of brokers, because a partition cannot
have more replicas than there are brokers to hold them, and it refuses
a broker with no rack assigned, because placing it would silently
break the guarantee the whole mechanism exists to provide. The planner
returns the chosen brokers in placement order, the first being the
preferred leader, and states the rack span, because a span of one is
the failure the feature was built to prevent, visible rather than
discovered during an outage."
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class RackAwarePlacement:
    # broker id -> rack id
    racks: dict[str, str] = field(default_factory=dict)

    def add_broker(self, broker: str, rack: str) -> None:
        if not rack:
            raise Invalid(
                f"broker '{broker}' has no rack assigned; placing it would "
                "silently break the rack-spreading guarantee"
            )
        self.racks[broker] = rack

    def place(self, replication_factor: int) -> list[str]:
        if replication_factor < 1:
            raise Invalid("replication factor must be at least one")
        if replication_factor > len(self.racks):
            raise Invalid(
                f"replication factor {replication_factor} exceeds the "
                f"{len(self.racks)} broker(s) available; a partition cannot "
                "have more replicas than brokers to hold them"
            )
        by_rack: dict[str, list[str]] = defaultdict(list)
        for broker, rack in sorted(self.racks.items()):
            by_rack[rack].append(broker)
        # round-robin across racks so replicas alternate racks before repeating
        order: list[str] = []
        queues = [list(v) for v in by_rack.values()]
        while queues:
            still: list[list[str]] = []
            for q in queues:
                order.append(q.pop(0))
                if q:
                    still.append(q)
            queues = still
        return order[:replication_factor]

    def rack_span(self, replicas: list[str]) -> int:
        return len({self.racks[r] for r in replicas})

    def note(self, replication_factor: int) -> str:
        chosen = self.place(replication_factor)
        span = self.rack_span(chosen)
        warn = "" if span > 1 else " (span of one, the failure this prevents)"
        return (
            f"{replication_factor} replica(s) span {span} rack(s){warn}; "
            "a whole-rack outage costs at most the replicas that rack held"
        )
