"""Cooperative rebalancing: stop only the partitions that actually move.

The old rebalance protocol was stop-the-world: every member
revoked every partition, the group reassigned from scratch, and
every member re-fetched, so a group of fifty paused entirely to
add one member. Cooperative rebalancing splits the change into
two rounds. In the first, the coordinator computes the new
assignment and asks each member to revoke only the partitions it
is losing, keeping the ones it retains live the whole time. In
the second, once the revoked partitions are free, they are
assigned to their new owners. The cost is one extra round trip;
the benefit is that the partitions that do not move never stop,
so the group's throughput dips instead of dropping to zero. The
invariant that makes it safe is that a partition is never owned
by two members across the rounds: it is revoked by its old owner
before it is assigned to its new one, because a partition
briefly owned by nobody is a pause and a partition briefly owned
by two is a duplicate, and the protocol chooses the pause every
time.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class CooperativeRebalance:
    current: dict[str, set[int]]
    target: dict[str, set[int]]
    revoked: dict[str, set[int]] = field(default_factory=dict)
    phase: str = "start"

    def to_revoke(self) -> dict[str, set[int]]:
        result = {}
        for member, held in self.current.items():
            losing = held - self.target.get(member, set())
            if losing:
                result[member] = losing
        return result

    def revoke_phase(self) -> str:
        if self.phase != "start":
            raise Invalid(
                "revoke happens once, at the start of a round"
            )
        self.revoked = self.to_revoke()
        for member, losing in self.revoked.items():
            self.current[member] = (
                self.current[member] - losing
            )
        self.phase = "revoked"
        moved = sum(len(v) for v in self.revoked.values())
        return (
            f"revoked {moved} partition(s); the ones staying "
            "put never paused"
        )

    def assign_phase(self) -> str:
        if self.phase != "revoked":
            raise Invalid("assign follows revoke, not precedes it")
        freed = set()
        for losing in self.revoked.values():
            freed |= losing
        for member, wanted in self.target.items():
            gaining = wanted - self.current.get(member, set())
            for part in gaining:
                if part not in freed and part in self._owned_now():
                    raise Invalid(
                        f"partition {part} would be owned twice; "
                        "the protocol pauses before it "
                        "duplicates"
                    )
            self.current[member] = set(wanted)
        self.phase = "done"
        return "assigned; no partition was ever owned by two"

    def _owned_now(self) -> set[int]:
        owned = set()
        for held in self.current.values():
            owned |= held
        return owned

    def never_double_owned(self) -> bool:
        seen = set()
        for held in self.current.values():
            if held & seen:
                return False
            seen |= held
        return True
