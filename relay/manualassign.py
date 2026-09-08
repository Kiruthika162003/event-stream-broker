"""Manual assign: take exactly these partitions, and own the failover yourself.

A consumer gets its partitions one of two ways, and they are
mutually exclusive. Subscribe hands the partitions to the group
coordinator, which assigns them, rebalances when membership
changes, and moves them to another consumer if this one dies, all
automatically, at the cost of the rebalances that coordination
brings. Manual assign takes a specific set of partitions directly,
with no group and no coordinator, so there are no rebalances, the
assignment is fixed and predictable, and the consumer reads exactly
the partitions it named. The cost of manual assign is the mirror of
subscribe's benefit: because there is no group, nothing moves a
manually-assigned consumer's partitions when it dies, so those
partitions simply stop being consumed until something restarts the
consumer or another process is told to take them, and the operator
owns that failover rather than the coordinator. Manual assign fits
a consumer that must read a fixed partition regardless of others, a
one-off tool reading one partition, or a system doing its own
partition-to-worker mapping, and it is wrong for a scalable
consumer group. The two modes cannot be mixed on one consumer,
because subscribe expects the coordinator to own the assignment
while assign expects the consumer to, and a consumer doing both
would have two owners of its partition set fighting. The manager
refuses to assign after subscribing and to subscribe after
assigning, and refuses an empty manual assignment, which reads
nothing. It reports that a manually-assigned partition has no
failover, because an operator expecting a dead consumer's
partitions to move needs to know that with manual assign they will
not, and the gap is theirs to close.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid

UNSET = "unset"
SUBSCRIBED = "subscribed"
ASSIGNED = "assigned"


@dataclass
class AssignmentMode:
    mode: str = UNSET
    partitions: set[str] = field(default_factory=set)

    def subscribe(self, topics: list[str]) -> str:
        if self.mode == ASSIGNED:
            raise Invalid(
                "cannot subscribe after a manual assign; the coordinator "
                "and the consumer would both own the partition set"
            )
        self.mode = SUBSCRIBED
        return (
            f"subscribed to {topics}; the coordinator assigns, rebalances, "
            "and fails over automatically"
        )

    def assign(self, partitions: list[str]) -> str:
        if self.mode == SUBSCRIBED:
            raise Invalid(
                "cannot manually assign after subscribing; the two modes "
                "have different owners of the assignment"
            )
        if not partitions:
            raise Invalid("an empty manual assignment reads nothing")
        self.mode = ASSIGNED
        self.partitions = set(partitions)
        return (
            f"assigned {sorted(self.partitions)} directly; no group, no "
            "rebalances, and no automatic failover"
        )

    def failover_note(self) -> str:
        if self.mode == SUBSCRIBED:
            return "subscribed: the coordinator moves partitions on failure"
        if self.mode == ASSIGNED:
            return (
                "manually assigned: nothing moves these partitions if the "
                "consumer dies; the operator owns that failover"
            )
        return "no partitions yet; neither subscribed nor assigned"
