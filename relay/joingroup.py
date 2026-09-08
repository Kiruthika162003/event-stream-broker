"""Join group: gather the members, pick one leader, agree on one assignor.

A rebalance begins with a join phase: the coordinator opens a
window and collects every member that wants in, and only once the
window closes does it decide the generation's shape. Two decisions
come out of the join. The first is the group leader, which the
coordinator picks as the first member to join, not because that
member is special but because exactly one member must compute the
assignment and the first joiner is an arbitrary but stable choice
the coordinator can make without coordinating. The leader is a
consumer like any other; it just also receives the full member list
and runs the assignor, returning the assignment the coordinator
then hands back to each member. The second decision is which
assignment strategy to use, and it must be one every member
supports, because a member handed an assignment computed by a
strategy it does not understand cannot honor it. Each member sends
the list of strategies it supports in preference order, and the
coordinator selects the most preferred strategy that appears in
every member's list, so a group mixing an old client that knows
only range with a new one that prefers cooperative-sticky falls
back to range, the common ground. The coordinator refuses to
complete a join with no strategy common to all members, because
there is no assignment it could compute that all would accept, and
it refuses to admit a member after the window closed into the
current generation, folding it into the next one instead, because
changing the membership after the leader computed the assignment
would hand out an assignment for a group that no longer matches.
The report names the leader and the chosen strategy, because a
rebalance that keeps choosing an unexpected strategy usually has
one member advertising a smaller strategy set than the operator
believes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class JoinPhase:
    generation: int
    window_open: bool = True
    members: list[str] = field(default_factory=list)
    strategies: dict[str, list[str]] = field(default_factory=dict)

    def join(self, member: str, supported: list[str]) -> str:
        if not self.window_open:
            return (
                f"{member} arrived after the window; folded into "
                f"generation {self.generation + 1}, not this one"
            )
        if member not in self.members:
            self.members.append(member)
        self.strategies[member] = list(supported)
        role = "leader" if self.members[0] == member else "follower"
        return f"{member} joined as {role} of generation {self.generation}"

    def leader(self) -> str:
        if not self.members:
            raise Invalid("no members joined; there is no leader")
        return self.members[0]

    def choose_strategy(self) -> str:
        if not self.members:
            raise Invalid("no members joined; nothing to assign")
        leader_prefs = self.strategies[self.members[0]]
        for strategy in leader_prefs:
            if all(strategy in self.strategies[m] for m in self.members):
                return strategy
        raise Invalid(
            "no assignment strategy is common to all members; there "
            "is no assignment every member would accept"
        )

    def close_window(self) -> str:
        self.window_open = False
        return (
            f"generation {self.generation}: leader {self.leader()}, "
            f"strategy {self.choose_strategy()}, {len(self.members)} "
            "member(s)"
        )
