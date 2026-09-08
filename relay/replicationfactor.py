"""Replication factor: you cannot keep more copies than you have brokers.

The replication factor is how many copies of each partition the
cluster keeps, and it is bounded by physical reality: a factor
higher than the broker count is impossible, because two copies of a
partition on the same broker are not two copies at all, they die
together when that broker does. So a topic created with a factor
above the broker count is refused rather than silently clamped,
because a clamp would give the operator fewer copies than they
asked for without telling them. The factor also carries a
durability meaning worth stating at creation. A factor of one is no
replication: the single copy is lost when its broker dies, so a
factor-one topic trades durability for cost and the operator should
know they made that trade. A factor of two survives one broker loss
but leaves no in-sync majority if the surviving copy is momentarily
behind, which is why three is the common floor for data that
matters. Rack awareness adds a second bound: to survive a rack
failure the replicas must span racks, so a factor of three across
two racks cannot place each copy in its own rack and at best
tolerates the loss of the smaller rack, and the validator names
that limit rather than reporting rack-fault-tolerance the placement
cannot deliver. The validator refuses a factor below one, which
would mean no copies at all, and reports the fault tolerance the
chosen factor actually provides, the number of simultaneous broker
losses the partition survives, because a factor picked without
knowing its fault tolerance is a durability decision made blind.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class ReplicationPlan:
    factor: int
    broker_count: int
    rack_count: int = 1

    def __post_init__(self) -> None:
        if self.factor < 1:
            raise Invalid("a replication factor below one keeps no copies")
        if self.factor > self.broker_count:
            raise Invalid(
                f"factor {self.factor} exceeds {self.broker_count} "
                "broker(s); two copies on one broker are not two copies, "
                "and a silent clamp would give fewer than asked"
            )

    def broker_fault_tolerance(self) -> int:
        return self.factor - 1

    def rack_fault_tolerance(self) -> str:
        if self.rack_count <= 1:
            return "one rack: no rack-failure tolerance regardless of factor"
        copies_per_rack = -(-self.factor // self.rack_count)
        survivable = self.rack_count - copies_per_rack
        if survivable < 1:
            return (
                f"factor {self.factor} across {self.rack_count} rack(s) "
                "cannot give each copy its own rack; it survives losing "
                "the smaller rack at best"
            )
        return f"survives losing {survivable} of {self.rack_count} rack(s)"

    def durability_note(self) -> str:
        if self.factor == 1:
            return (
                "factor 1 is no replication; the copy dies with its "
                "broker, a durability-for-cost trade to make knowingly"
            )
        return (
            f"factor {self.factor} survives {self.broker_fault_tolerance()} "
            "simultaneous broker loss(es); three is the common floor for "
            "data that matters"
        )
