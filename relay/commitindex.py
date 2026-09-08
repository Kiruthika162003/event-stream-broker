"""Commit index: a majority replicated it, but a prior term needs one more rule.

A replicated log commits an entry once a majority of nodes have it,
and the naive rule is to advance the commit index to the highest
index a majority has stored. That rule is correct for entries from
the current leader's term and subtly wrong for entries from an
earlier term, a trap famous enough to have a name, the figure-8.
The danger: a leader sees that an old entry from a previous term is
now stored on a majority and commits it, but a different leader
could still be elected that does not have that entry and overwrites
it, because the majority that stored it was not enough to protect
an entry the new leader's election did not require. The fix is a
rule Raft states precisely: a leader commits an entry from an
earlier term only indirectly, by first committing an entry from its
own current term at a higher index, because once a current-term
entry is committed on a majority, the log-matching property carries
every preceding entry with it, safely. So the commit index advances
freely for current-term entries a majority holds, and for older
entries only once a newer current-term entry has been committed. The
tracker holds the current term and each entry's term, advances the
commit index to the majority-replicated frontier but never past a
prior-term entry unless a current-term entry beyond it is also
committed, and it refuses to commit a prior-term entry directly,
naming the figure-8. It reports what is holding the commit index
back, because a commit index stuck below a majority-replicated
prior-term entry is not a bug, it is this rule protecting against an
overwrite, and knowing that stops an operator from forcing a commit
that could lose data."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class CommitIndex:
    current_term: int
    entry_terms: dict[int, int] = field(default_factory=dict)
    voters: int = 3
    commit_index: int = 0

    def majority(self) -> int:
        return self.voters // 2 + 1

    def try_advance(self, index: int, replica_count: int) -> str:
        if index not in self.entry_terms:
            raise Invalid(f"no entry at index {index}")
        if replica_count < self.majority():
            raise Invalid(
                f"index {index} on only {replica_count} of {self.voters}, "
                f"below majority {self.majority()}; not committable yet"
            )
        entry_term = self.entry_terms[index]
        if entry_term < self.current_term:
            raise Invalid(
                f"index {index} is from term {entry_term}, older than the "
                f"current {self.current_term}; committing it directly is the "
                "figure-8 bug, a new leader could overwrite it; commit a "
                "current-term entry beyond it first"
            )
        self.commit_index = max(self.commit_index, index)
        return f"committed to index {index} (current-term entry, majority holds it)"

    def commit_prior_via_current(self, prior_index: int, current_index: int) -> str:
        if self.entry_terms.get(current_index) != self.current_term:
            raise Invalid(
                f"index {current_index} is not a current-term entry; it cannot "
                "carry a prior-term entry to commit"
            )
        if current_index < prior_index:
            raise Invalid("the current-term entry must be beyond the prior one")
        self.commit_index = max(self.commit_index, current_index)
        return (
            f"committed through {current_index}; the prior-term entry at "
            f"{prior_index} is now safely committed by log matching"
        )
