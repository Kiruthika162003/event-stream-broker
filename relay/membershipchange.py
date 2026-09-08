"""Membership change: move the voter set one at a time, or risk two majorities.

Changing which nodes vote in a quorum, adding a replica, retiring
one, is dangerous done carelessly, because for a moment the cluster
can hold two different ideas of who votes, and if those two voter
sets each have a majority that does not overlap the other, two
leaders can be elected at once, a split brain that a quorum exists
to prevent. The danger comes from changing more than one voter at a
time. Consider going from three voters to five in one step: during
the change, some nodes think the set is the old three, needing a
majority of two, and some think it is the new five, needing three,
and it is possible for two of the old and three of the new to each
form a majority of their own view with no node in both, electing
two leaders. Changing by a single voter avoids it: adding or
removing one keeps every old majority and every new majority
overlapping in at least one node, because the sets differ by only
one member, so no two disjoint majorities can form and the change
is safe at every instant. To grow or shrink by more than one, the
cluster makes a sequence of single-voter changes, each safe, rather
than one big jump. The validator checks a proposed voter set against
the current, allowing it only if they differ by exactly one member,
and computes the new majority. It refuses a change of more than one
voter, naming the split-brain risk, and refuses a change to an
empty voter set, which could not elect anyone. It reports the
majority before and after, because an operator growing the cluster
needs to see that the majority rises with it, so a cluster that
tolerated one failure at three voters tolerates two at five, the
whole point of adding them."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class Membership:
    voters: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not self.voters:
            raise Invalid("a voter set cannot be empty")

    def majority(self) -> int:
        return len(self.voters) // 2 + 1

    def change_to(self, proposed: set[str]) -> str:
        if not proposed:
            raise Invalid("cannot change to an empty voter set; it elects no one")
        diff = len(self.voters.symmetric_difference(proposed))
        if diff == 0:
            return "no change"
        if diff > 1:
            raise Invalid(
                f"the change moves {diff} voters at once; two disjoint "
                "majorities could form and elect two leaders, a split brain; "
                "change one voter at a time"
            )
        old_majority = self.majority()
        self.voters = set(proposed)
        return (
            f"changed by one voter; majority {old_majority} -> {self.majority()}, "
            "every old and new majority still overlapping, safe"
        )

    def failures_tolerated(self) -> int:
        return len(self.voters) - self.majority()
