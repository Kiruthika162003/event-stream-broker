"""Assign versus subscribe: two ways to own partitions, never both at once.

A consumer gets partitions one of two ways. Subscribe joins a
group and lets the coordinator assign partitions, with automatic
rebalancing as members come and go, which is what most consumers
want. Assign takes specific partitions manually, no group, no
rebalancing, the consumer owns exactly what it named, which is
what a consumer needs when it manages its own partition-to-work
mapping, a static stream processor pinned to partitions by shard.
The rule that trips people is that a single consumer cannot do
both: it cannot subscribe to a group and also manually assign
partitions, because the two ownership models conflict, the group
would try to rebalance partitions the manual assignment considers
fixed, and the consumer would end up owning partitions by two
contradictory authorities. The mode guard makes the modes
mutually exclusive and refuses the switch mid-flight without an
explicit unsubscribe or unassign first, because silently
dropping one mode's ownership when the other is invoked is how a
consumer ends up reading partitions it thinks it released.
Manual assignment also forfeits the group's protections, no
automatic rebalancing means a manually-assigned consumer that
dies leaves its partitions unowned until something external
notices, so the guard names that tradeoff when assignment is
chosen, because a consumer that picked manual assignment for its
control should know it also picked manual failure handling.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid

NONE = "none"
SUBSCRIBED = "subscribed"
ASSIGNED = "assigned"


@dataclass
class ConsumerMode:
    mode: str = NONE
    partitions: set[int] = field(default_factory=set)

    def subscribe(self, group: str) -> str:
        if self.mode == ASSIGNED:
            raise Invalid(
                "cannot subscribe while manually assigned; the "
                "group would rebalance partitions the assignment "
                "considers fixed. Unassign first"
            )
        self.mode = SUBSCRIBED
        return (
            f"subscribed to {group}: the coordinator assigns and "
            "rebalances, the group's protections apply"
        )

    def assign(self, partitions: set[int]) -> str:
        if self.mode == SUBSCRIBED:
            raise Invalid(
                "cannot assign while subscribed; two ownership "
                "authorities would contradict. Unsubscribe first"
            )
        self.mode = ASSIGNED
        self.partitions = set(partitions)
        return (
            f"assigned {sorted(partitions)}: no rebalancing, and "
            "no automatic failover, so manual assignment is also "
            "manual failure handling"
        )

    def release(self) -> str:
        was = self.mode
        self.mode = NONE
        self.partitions = set()
        return f"released {was} ownership"
