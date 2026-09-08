"""Static assignor: a fixed partition-to-member map that a restart does not disturb.

Most partition assignment is dynamic: the group balances partitions
across whatever members are present, and every join or leave triggers
a rebalance that can move partitions between members. For some
workloads that churn is the problem, not the feature. A member with
large local state built up for its partitions pays to rebuild that
state every time it is handed different partitions, and a rolling
restart of such a group, each member bouncing in turn, can trigger a
cascade of rebalances that each shuffle assignments. A static assignor
pins each partition to a named member by configuration, so the
assignment is the same every time it is computed, and a member that
restarts and rejoins under the same name gets exactly its old
partitions back with no rebalance and no state rebuild. The cost is
that a statically assigned partition whose member is gone is not
reassigned to a surviving member, because the whole point is that
assignments do not move; that partition simply goes unconsumed until
its member returns, a deliberate choice to trade automatic failover
for assignment stability. The assignor holds the configured map, gives
a member its partitions, tells which member owns a partition, and
lists partitions whose member is currently absent, the ones going
unconsumed. It refuses to assign one partition to two members, because
overlapping ownership is the double-consumption a partition assignment
exists to prevent, and refuses a lookup of an unmapped partition. It
reports the unconsumed partitions, because with static assignment a
member staying down is not self-healing, and that list is the manual
attention the stability trade requires."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid, Missing


@dataclass
class StaticAssignor:
    # partition -> the member configured to own it
    owner_of: dict[str, str] = field(default_factory=dict)
    present: set[str] = field(default_factory=set)

    def assign(self, partition: str, member: str) -> None:
        existing = self.owner_of.get(partition)
        if existing is not None and existing != member:
            raise Invalid(
                f"partition '{partition}' is already assigned to '{existing}'; "
                "overlapping ownership is the double-consumption assignment "
                "exists to prevent"
            )
        self.owner_of[partition] = member

    def mark_present(self, member: str, *, present: bool = True) -> None:
        if present:
            self.present.add(member)
        else:
            self.present.discard(member)

    def partitions_for(self, member: str) -> list[str]:
        return sorted(p for p, m in self.owner_of.items() if m == member)

    def owner(self, partition: str) -> str:
        if partition not in self.owner_of:
            raise Missing(f"partition '{partition}' is not in the static map")
        return self.owner_of[partition]

    def unconsumed(self) -> list[str]:
        # partitions whose configured member is currently absent
        return sorted(
            p for p, m in self.owner_of.items() if m not in self.present
        )

    def note(self) -> str:
        absent = self.unconsumed()
        return (
            f"{len(self.owner_of)} partition(s) statically mapped, "
            f"{len(absent)} unconsumed: {absent}; static assignment does not "
            "self-heal, that list is the manual attention the stability costs"
        )
