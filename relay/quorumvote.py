"""Quorum vote: a candidate wins only with a majority whose logs it covers.

The metadata quorum elects a leader by vote, and two rules
together keep the election safe. The first is majority: a
candidate needs votes from more than half the voters, because two
candidates cannot both hold a majority of the same voter set, so
at most one wins a term and the cluster cannot fork into two
leaders. The second is the log-recency rule: a voter grants its
vote only to a candidate whose log is at least as up to date as
its own, judged first by the last term in the log and then by
length, so a candidate missing committed records cannot collect a
majority, because every voter that holds those records refuses it.
Together these guarantee the winner's log contains every record
that any majority committed, which is the property that lets a new
leader serve without losing acknowledged data. The counter refuses
to grant two votes in the same term from one voter, because a voter
that voted twice could help two candidates each reach a majority
and split the term, the exact fork the majority rule exists to
prevent. A candidate also refuses to count a vote from a stale
term, because a vote cast for an earlier election says nothing
about this one. The tally reports whether the majority was reached
and, when it was not, how many more votes were needed, because a
candidate that fell one short of a five-node quorum learns
something different from one that got a single vote: the first was
nearly elected, the second was rejected by almost everyone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Fenced, Invalid


@dataclass(frozen=True)
class LogEnd:
    last_term: int
    length: int

    def at_least_as_current_as(self, other: LogEnd) -> bool:
        if self.last_term != other.last_term:
            return self.last_term > other.last_term
        return self.length >= other.length


@dataclass
class Election:
    term: int
    voters: int
    granted: set[str] = field(default_factory=set)
    voted_terms: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.voters < 1:
            raise Invalid("an election needs at least one voter")

    def majority(self) -> int:
        return self.voters // 2 + 1

    def request_vote(
        self,
        voter: str,
        candidate_log: LogEnd,
        voter_log: LogEnd,
    ) -> bool:
        if self.voted_terms.get(voter) == self.term:
            raise Fenced(
                f"{voter} already voted in term {self.term}; a "
                "second vote could split the term between two "
                "candidates"
            )
        self.voted_terms[voter] = self.term
        if not candidate_log.at_least_as_current_as(voter_log):
            return False
        self.granted.add(voter)
        return True

    def won(self) -> bool:
        return len(self.granted) >= self.majority()

    def tally(self) -> str:
        need = self.majority()
        have = len(self.granted)
        if have >= need:
            return f"won term {self.term}: {have}/{self.voters}, majority {need}"
        return (
            f"lost term {self.term}: {have}/{self.voters}, needed "
            f"{need}, short by {need - have}"
        )
