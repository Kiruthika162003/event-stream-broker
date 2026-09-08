"""Group states: a consumer group is a state machine, and the states gate work.

A consumer group is not always ready to consume, and pretending
it is causes the subtle bugs. It moves through states: Empty, no
members; PreparingRebalance, members are joining or leaving and
the assignment is being recomputed; CompletingRebalance, the
assignment is decided and members are receiving it; and Stable,
everyone has their partitions and consumption proceeds. The rule
that these states enforce is that consumption and offset commits
are only valid in Stable, because a commit during a rebalance
commits against an assignment that is about to change, and a
member that keeps consuming while the group rebalances processes
partitions it may be about to lose, the double-processing the
rebalance exists to prevent. The transitions are constrained: a
join or leave from Stable moves to PreparingRebalance, and the
group cannot skip from PreparingRebalance straight to Stable
without passing through CompletingRebalance, because the
assignment must be distributed before it is live. The generation
id increments on entering PreparingRebalance and fences stale
commits: a commit carrying an old generation is from a member
that has not noticed the rebalance, and accepting it would apply
a decision from a superseded assignment, so it is rejected with
the generation gap named.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

EMPTY = "Empty"
PREPARING = "PreparingRebalance"
COMPLETING = "CompletingRebalance"
STABLE = "Stable"

ALLOWED = {
    EMPTY: {PREPARING},
    PREPARING: {COMPLETING, EMPTY},
    COMPLETING: {STABLE, PREPARING},
    STABLE: {PREPARING},
}


@dataclass
class GroupStateMachine:
    state: str = EMPTY
    generation: int = 0

    def transition(self, target: str) -> str:
        if target not in ALLOWED.get(self.state, set()):
            raise Invalid(
                f"cannot go {self.state} -> {target}; the "
                "assignment must be distributed before it is "
                "live, so no shortcut past CompletingRebalance"
            )
        if target == PREPARING:
            self.generation += 1
        self.state = target
        return f"{self.state} (generation {self.generation})"

    def may_consume(self) -> bool:
        return self.state == STABLE

    def commit(self, generation: int) -> str:
        if self.state != STABLE:
            raise Invalid(
                f"cannot commit in {self.state}; a commit during "
                "a rebalance is against an assignment about to "
                "change"
            )
        if generation < self.generation:
            raise Invalid(
                f"generation {generation} is behind "
                f"{self.generation}; this commit is from a member "
                "that has not noticed the rebalance and applies a "
                "superseded assignment"
            )
        return f"commit accepted at generation {self.generation}"
