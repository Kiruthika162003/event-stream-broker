"""List groups: a fleet of groups, filtered by state, and which are dead weight.

An operator managing a cluster does not ask about one group but
about all of them, and the useful questions are about state: which
groups are stable and consuming, which are stuck rebalancing, and
which are empty and holding committed offsets for no active
consumer. ListGroups answers by returning every group with its
current state, and the value is in the filtering, because a
thousand-group cluster is unreadable as a flat list and readable as
a handful of stuck or empty ones. An empty group, one with no
members but retained committed offsets, is the interesting case: it
is not consuming yet it counts against the offsets topic and its
offsets keep the coordinator remembering it, so an operator
cleaning up looks for empty groups whose offsets have aged past use
and are safe to delete. A group in a rebalancing state for a long
time is the other interesting case: a rebalance is supposed to be
brief, so a group stuck preparing or completing is a symptom of a
member that joined and never sent its assignment or one that keeps
timing out, which the list surfaces by state rather than making the
operator poll each group. The lister refuses to report a group in
the dead state, because a dead group has been removed and listing
it as if present would tell an operator to act on something already
gone. The report counts groups by state, because the shape of a
healthy cluster is mostly stable with a few empty and none stuck,
and a cluster with many rebalancing groups is one where something
is flapping.
"""

from __future__ import annotations

from dataclasses import dataclass, field

STABLE = "Stable"
EMPTY = "Empty"
PREPARING = "PreparingRebalance"
COMPLETING = "CompletingRebalance"
DEAD = "Dead"
_REBALANCING = (PREPARING, COMPLETING)


@dataclass(frozen=True)
class GroupInfo:
    group_id: str
    state: str
    members: int
    offset_age_ticks: int


@dataclass
class GroupList:
    groups: list[GroupInfo] = field(default_factory=list)

    def visible(self) -> list[GroupInfo]:
        return [g for g in self.groups if g.state != DEAD]

    def in_state(self, state: str) -> list[GroupInfo]:
        return [g for g in self.visible() if g.state == state]

    def stuck_rebalancing(self, threshold: int) -> list[str]:
        return [
            g.group_id
            for g in self.visible()
            if g.state in _REBALANCING and g.offset_age_ticks >= threshold
        ]

    def deletable_empty(self, offset_age_limit: int) -> list[str]:
        return [
            g.group_id
            for g in self.visible()
            if g.state == EMPTY
            and g.members == 0
            and g.offset_age_ticks >= offset_age_limit
        ]

    def by_state(self) -> str:
        counts: dict[str, int] = {}
        for g in self.visible():
            counts[g.state] = counts.get(g.state, 0) + 1
        parts = ", ".join(f"{s}: {n}" for s, n in sorted(counts.items()))
        return (
            f"{parts}; a healthy cluster is mostly stable with a few "
            "empty and none stuck rebalancing"
        )
