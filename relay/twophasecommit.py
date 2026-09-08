"""Two-phase commit: everyone votes, then everyone learns the one verdict.

Committing a change across several participants atomically, all
apply it or none do, is what two-phase commit coordinates. In the
first phase the coordinator asks every participant to prepare, and
each votes yes only if it can guarantee it will be able to commit
if asked, having written the change durably in a pending state, or
no if it cannot. In the second phase the coordinator decides: commit
if every participant voted yes, abort if any voted no, and it sends
that one verdict to all, so either all commit or all abort, never a
split. The guarantee rests on the prepare vote being a promise: a
participant that voted yes has given up its right to abort
unilaterally and must commit when told, which is why prepare must
make the change durable first, or a crash after voting yes could
leave it unable to keep the promise. The famous weakness is the
blocking problem: a participant that voted yes and then loses
contact with the coordinator, because the coordinator crashed after
collecting votes but before sending the verdict, is stuck, it
cannot abort, having promised to commit, and cannot commit, not
knowing the verdict, so it blocks holding its resources until the
coordinator returns, which is why 2PC is not partition-tolerant and
protocols like Raft or 3PC exist. The coordinator collects votes,
decides commit only if unanimous yes, and refuses to commit if any
voted no, and it refuses a participant changing its vote after
casting one, since a vote is a promise. It reports whether the
outcome is decided or blocked, because a transaction blocked on a
missing coordinator is the 2PC weakness in action, holding
resources until the coordinator is heard from."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid

YES = "yes"
NO = "no"
COMMIT = "commit"
ABORT = "abort"


@dataclass
class TwoPhaseCommit:
    participants: set[str]
    votes: dict[str, str] = field(default_factory=dict)
    decision: str = ""

    def __post_init__(self) -> None:
        if not self.participants:
            raise Invalid("a transaction needs at least one participant")

    def vote(self, participant: str, vote: str) -> str:
        if participant not in self.participants:
            raise Invalid(f"'{participant}' is not a participant")
        if vote not in (YES, NO):
            raise Invalid("a vote is yes or no")
        if participant in self.votes:
            raise Invalid(
                f"'{participant}' already voted '{self.votes[participant]}'; a "
                "vote is a promise and cannot be changed"
            )
        self.votes[participant] = vote
        return f"'{participant}' voted {vote}"

    def all_voted(self) -> bool:
        return set(self.votes) == self.participants

    def decide(self) -> str:
        if not self.all_voted():
            raise Invalid(
                f"only {len(self.votes)}/{len(self.participants)} voted; the "
                "coordinator waits for all before deciding"
            )
        self.decision = COMMIT if all(v == YES for v in self.votes.values()) else ABORT
        return f"decided {self.decision}"

    def participant_state(self, participant: str, heard_decision: bool) -> str:
        vote = self.votes.get(participant)
        if vote != YES:
            return f"'{participant}' has not promised to commit"
        if heard_decision and self.decision:
            return f"'{participant}' applies the {self.decision}"
        return (
            f"'{participant}' voted yes and is BLOCKED: it cannot abort "
            "(promised) nor commit (verdict unknown), holding resources until "
            "the coordinator is heard from, the 2PC weakness"
        )
