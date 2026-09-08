"""Assignment validation: no partition owned twice, none silently dropped.

Any partition assignment a rebalance produces must satisfy two
invariants that a clever assignor can violate while looking
correct. First, no partition may be assigned to two members,
because two consumers reading one partition double-process every
record and commit conflicting offsets, the consumer-side
corruption that is invisible until the downstream shows
duplicates. Second, every partition must be assigned to exactly
one member, because a partition assigned to nobody is read by
nobody, its lag grows forever, and it is the silent gap that a
per-member view never reveals since each member's list looks
complete. The validator checks both against the full partition
set, not against the members' lists alone, because the bug is
always in the relationship between what was assigned and what
exists: a member list can be internally consistent and still miss
a partition or share one. It reports the specific violations,
which partitions are double-owned and by whom, which are
orphaned, because an assignor that produced a bad assignment
needs to know exactly what to fix, and a generic invalid-
assignment rejection sends its author guessing. The validator is
the gate a rebalance result passes through before it goes live,
because an assignment applied and then found broken has already
double-processed records, and catching it at validation is the
difference between a rejected proposal and a data incident.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class AssignmentValidator:
    all_partitions: set[int]

    def double_owned(
        self, assignment: dict[str, set[int]]
    ) -> dict[int, list[str]]:
        owners: dict[int, list[str]] = {}
        for member, partitions in assignment.items():
            for partition in partitions:
                owners.setdefault(partition, []).append(member)
        return {
            partition: sorted(members)
            for partition, members in owners.items()
            if len(members) > 1
        }

    def orphaned(
        self, assignment: dict[str, set[int]]
    ) -> set[int]:
        assigned = set()
        for partitions in assignment.values():
            assigned |= partitions
        return self.all_partitions - assigned

    def validate(self, assignment: dict[str, set[int]]) -> str:
        double = self.double_owned(assignment)
        orphans = self.orphaned(assignment)
        problems = []
        if double:
            pairs = "; ".join(
                f"{p} by {', '.join(m)}"
                for p, m in sorted(double.items())
            )
            problems.append(
                f"double-owned ({pairs}): two consumers "
                "double-process and commit conflicting offsets"
            )
        if orphans:
            problems.append(
                f"orphaned {sorted(orphans)}: read by nobody, lag "
                "grows forever, the silent gap a per-member view "
                "never reveals"
            )
        if problems:
            raise Invalid(
                "assignment rejected before going live: "
                + "; ".join(problems)
            )
        return (
            f"assignment valid: {len(self.all_partitions)} "
            "partition(s) each owned exactly once"
        )
