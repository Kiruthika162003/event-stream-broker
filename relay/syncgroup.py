"""Sync group: the leader hands in the whole plan, each member gets its slice.

After the join phase names a leader and a strategy, the sync phase
distributes the assignment. Only the leader computed it, so only
the leader submits it: the leader sends the coordinator the full
map of member to partitions, while every follower sends an empty
sync request and blocks, waiting to be told its share. The
coordinator caches the leader's map and answers each member's sync
with just that member's partitions, so no consumer ever learns the
whole group's assignment, only its own, which is all it needs. This
split is why a follower cannot submit an assignment: it did not run
the assignor and its map would be a guess, so the coordinator
refuses a non-leader that tries to submit one, treating it as a
confused or malicious client. The coordinator also refuses a
leader's assignment that does not cover exactly the members that
joined, because an assignment missing a member leaves that member
with nothing to consume while an assignment naming a member that
did not join sends partitions to a consumer that is not there, and
either way some partitions go unconsumed. The plan must partition
the topic's partitions without overlap, so the coordinator refuses
a map that assigns one partition to two members, the double-owner
that would process every record twice. The report states each
member's share count, because a sync that handed one member every
partition and the rest none is a broken assignor, visible in the
shares long before it shows up as one consumer melting down while
the others idle.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class SyncPhase:
    leader: str
    members: set[str]
    assignment: dict[str, list[int]] = field(default_factory=dict)
    submitted: bool = False

    def submit(self, member: str, plan: dict[str, list[int]]) -> str:
        if member != self.leader:
            raise Invalid(
                f"{member} is a follower and did not run the "
                "assignor; its map would be a guess, so a non-leader "
                "submission is refused"
            )
        if set(plan) != self.members:
            raise Invalid(
                "the assignment must cover exactly the members that "
                "joined; a missing member consumes nothing and an "
                "extra one strands partitions"
            )
        seen: set[int] = set()
        for parts in plan.values():
            for p in parts:
                if p in seen:
                    raise Invalid(
                        f"partition {p} is assigned to two members; "
                        "the double owner processes every record twice"
                    )
                seen.add(p)
        self.assignment = {m: list(ps) for m, ps in plan.items()}
        self.submitted = True
        return f"leader {member} submitted a plan for {len(plan)} member(s)"

    def slice_for(self, member: str) -> list[int]:
        if not self.submitted:
            raise Invalid("no assignment submitted yet; the follower waits")
        if member not in self.members:
            raise Invalid(f"{member} is not in this generation")
        return self.assignment.get(member, [])

    def shares(self) -> str:
        counts = {m: len(self.assignment.get(m, [])) for m in self.members}
        hi = max(counts.values())
        lo = min(counts.values())
        return (
            f"shares {counts}; spread {hi - lo}, and a spread near the "
            "total means a broken assignor piling one member up while "
            "the rest idle"
        )
