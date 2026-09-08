"""Describe quorum: is the metadata quorum healthy, and which voter is behind.

The metadata quorum's health is not visible from whether the
cluster is currently up, because a quorum can be one failure away
from losing its majority while everything still works, and
describe-quorum is how an operator sees that margin before it
matters. It reports the current leader, each voter with how far its
replicated offset lags the leader's, and the observers. The number
that matters is how many voters are caught up enough to form a
majority right now: a five-voter quorum needs three, so it
tolerates two lagging, but if three of the five have fallen behind,
the quorum is already unable to commit and the cluster's metadata
is frozen even though brokers are still serving data from the last
known state. A voter lagging is worse than an observer lagging,
because an observer does not count toward the majority, so the tool
separates the two and weighs voter lag heavily. The diagnostic
computes the caught-up voter count against the majority and flags
the quorum as at-risk when losing one more caught-up voter would
drop below the majority, the margin an operator watches. It refuses
to report a quorum healthy when the caught-up voters are already
below the majority, because that is a quorum that cannot commit and
calling it healthy hides an outage in progress, and it names the
most-lagged voter as the one to investigate, since bringing it back
into the caught-up set restores the margin. The report states the
margin in voters, because the difference between a quorum with two
spare caught-up voters and one with none is the difference between
a comfortable cluster and one a single failure will freeze.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class QuorumStatus:
    leader_offset: int
    voter_offsets: dict[str, int] = field(default_factory=dict)
    max_lag: int = 100

    def __post_init__(self) -> None:
        if not self.voter_offsets:
            raise Invalid("a quorum needs voters")

    def majority(self) -> int:
        return len(self.voter_offsets) // 2 + 1

    def caught_up(self) -> list[str]:
        return [
            v
            for v, off in self.voter_offsets.items()
            if self.leader_offset - off <= self.max_lag
        ]

    def can_commit(self) -> bool:
        return len(self.caught_up()) >= self.majority()

    def at_risk(self) -> bool:
        return len(self.caught_up()) == self.majority()

    def most_lagged(self) -> str:
        return min(self.voter_offsets, key=self.voter_offsets.get)

    def margin(self) -> int:
        return len(self.caught_up()) - self.majority()

    def report(self) -> str:
        if not self.can_commit():
            return (
                f"UNHEALTHY: only {len(self.caught_up())} of "
                f"{len(self.voter_offsets)} voters caught up, below the "
                f"majority {self.majority()}; the quorum cannot commit and "
                "metadata is frozen, an outage in progress"
            )
        state = "AT RISK" if self.at_risk() else "healthy"
        return (
            f"{state}: {len(self.caught_up())} caught up, majority "
            f"{self.majority()}, margin {self.margin()} voter(s); most "
            f"lagged '{self.most_lagged()}', the one to bring back"
        )
