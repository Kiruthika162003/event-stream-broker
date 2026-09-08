"""Rebalancing: when membership changes, move as few partitions as possible.

A consumer group's partitions are divided among its live
members, and every join or leave forces a reassignment. The
naive strategy sorts and slices fresh each time, which is
balanced and catastrophic: a single member joining a group of
twenty can reshuffle nearly every partition, and every moved
partition pays a stop-the-world revoke, a state flush, and a
cold re-fetch. Sticky assignment keeps a member on the
partitions it already owns wherever balance permits, moving
only the partitions that must move to absorb the change, and
the report proves it by counting moved-versus-total, because
the difference between sticky and naive is invisible until a
production group with warm local state rebalances and either
blinks or stalls. Balance is still enforced: no member may hold
more than one partition above the floor, so stickiness buys
continuity without buying a hot member nobody can dislodge.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


def _balanced_counts(
    partitions: int, members: int
) -> list[int]:
    base = partitions // members
    extra = partitions % members
    return [
        base + (1 if index < extra else 0)
        for index in range(members)
    ]


@dataclass
class Assignment:
    by_member: dict[str, list[int]]

    def balanced(self) -> bool:
        counts = sorted(
            len(v) for v in self.by_member.values()
        )
        return counts[-1] - counts[0] <= 1

    def owner_of(self, partition: int) -> str | None:
        for member, parts in self.by_member.items():
            if partition in parts:
                return member
        return None


def sticky_assign(
    partitions: list[int],
    members: list[str],
    previous: Assignment | None = None,
) -> tuple[Assignment, int]:
    if not members:
        raise _no_members()
    members = sorted(members)
    targets = dict(
        zip(
            members,
            _balanced_counts(len(partitions), len(members)),
            strict=True,
        )
    )
    result: dict[str, list[int]] = {m: [] for m in members}
    unassigned = list(partitions)
    moved = 0
    if previous is not None:
        for member in members:
            for part in previous.by_member.get(member, []):
                if (
                    part in unassigned
                    and len(result[member]) < targets[member]
                ):
                    result[member].append(part)
                    unassigned.remove(part)
    kept_owner = {
        part: previous.owner_of(part)
        if previous is not None
        else None
        for part in partitions
    }
    for part in sorted(unassigned):
        target_member = min(
            members,
            key=lambda m: (
                len(result[m]) - targets[m],
                m,
            ),
        )
        result[target_member].append(part)
        relocated = kept_owner[part] not in (None, target_member)
        newly_placed = (
            kept_owner[part] is None and previous is not None
        )
        if relocated or newly_placed:
            moved += 1
    for parts in result.values():
        parts.sort()
    return Assignment(by_member=result), moved


def _no_members() -> Invalid:
    return Invalid("a group with no members owns no partitions")


def naive_moved(
    partitions: list[int],
    members: list[str],
    previous: Assignment,
) -> int:
    members = sorted(members)
    fresh: dict[str, list[int]] = {m: [] for m in members}
    for index, part in enumerate(sorted(partitions)):
        fresh[members[index % len(members)]].append(part)
    moved = 0
    for member, parts in fresh.items():
        for part in parts:
            if previous.owner_of(part) not in (None, member):
                moved += 1
    return moved
