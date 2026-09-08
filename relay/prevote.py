"""Pre-vote: ask before campaigning, so a partitioned node does not disrupt.

A node that cannot reach the leader assumes the leader is gone and
starts an election, and in the basic protocol it does that by
incrementing its term and asking for votes. That is fine when the
leader really failed, but harmful when the node itself is the
problem, partitioned away while the leader and the rest are healthy:
the isolated node keeps timing out, keeps incrementing its term, and
its term races far ahead of the cluster's, so when the partition
heals and it rejoins, its higher term forces the healthy leader to
step down and the whole cluster to hold a new election it did not
need, a disruption caused by the node that was never going to win.
Pre-vote prevents it by adding a probe before the real campaign: the
candidate asks peers whether they would grant it a vote given its
log, without anyone incrementing a term, and only if a majority
say yes does it increment its term and run the real election. A
partitioned node's pre-vote fails, because the peers it can reach
still have a leader and would not vote, so it never increments its
term, and its term stays in step with the cluster, so its eventual
rejoin is quiet. The check that makes pre-vote work is that a peer
grants a pre-vote only if it has not heard from a leader recently
and the candidate's log is current, the same conditions as a real
vote but without the term bump. The prevote collects grants, decides
whether a real election is warranted, and refuses to campaign
without a pre-vote majority. It reports whether the campaign is
warranted or the node should stand down, because a node repeatedly
failing pre-vote is one that is itself partitioned, not one seeing a
dead leader, and standing down is the correct, non-disruptive
response."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class PreVote:
    voters: int
    grants: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.voters < 1:
            raise Invalid("need at least one voter")

    def majority(self) -> int:
        return self.voters // 2 + 1

    def request(self, peer: str, heard_leader_recently: bool, log_current: bool) -> bool:
        # a peer grants a pre-vote only if it sees no live leader and the
        # candidate's log is current, the real-vote conditions without a bump
        if heard_leader_recently or not log_current:
            return False
        self.grants.add(peer)
        return True

    def warranted(self) -> bool:
        return len(self.grants) >= self.majority()

    def campaign(self) -> str:
        if not self.warranted():
            raise Invalid(
                f"pre-vote got {len(self.grants)}/{self.voters}, below majority "
                f"{self.majority()}; this node is partitioned, not seeing a dead "
                "leader, so it stands down without bumping its term"
            )
        return "pre-vote passed; increment the term and run the real election"

    def report(self) -> str:
        if self.warranted():
            return (
                f"campaign warranted, {len(self.grants)} pre-vote(s); a real "
                "leader may be gone"
            )
        return (
            f"only {len(self.grants)} pre-vote(s); stand down, the node is "
            "likely partitioned and bumping its term would disrupt a healthy "
            "cluster on rejoin"
        )
