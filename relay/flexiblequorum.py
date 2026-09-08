"""Flexible quorum: election and replication quorums need only intersect.

The usual rule that both a leader election and a commit require a
majority is stricter than consensus actually needs. The real
requirement is that the election quorum and the replication quorum
intersect, so that a newly elected leader's election quorum overlaps
the replication quorum of any committed entry, guaranteeing the new
leader has seen that entry. Two majorities always intersect, which
is why the majority rule works, but it is not the only way to make
two sets intersect: any two quorums whose sizes sum to more than the
node count must share a node, so an election quorum of size Q1 and a
replication quorum of size Q2 are safe whenever Q1 plus Q2 exceeds
N. This unlocks a tradeoff the majority rule hides. Commits happen
constantly and elections rarely, so making the replication quorum
smaller speeds up the common path at the cost of a larger election
quorum on the rare path: with five nodes, a replication quorum of
two and an election quorum of four intersect, so every commit needs
only two acknowledgements instead of three, faster, while an
election needs four instead of three, slower but rare. The tradeoff
is bounded by intersection: shrinking the replication quorum forces
the election quorum up one for one, and pushing the replication
quorum to one forces the election quorum to all nodes, meaning an
election cannot tolerate any node being down. The validator checks
that a Q1 and Q2 intersect for a given N, computes the failures each
tolerates, and refuses a pair that does not intersect, the
unsafe configuration where a new leader could miss a committed
entry. It reports the tradeoff, because a cluster tuning for commit
speed by shrinking the replication quorum should see the election
availability it is spending to buy it."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class FlexibleQuorum:
    nodes: int
    election_quorum: int
    replication_quorum: int

    def __post_init__(self) -> None:
        if self.nodes < 1:
            raise Invalid("need at least one node")
        for q in (self.election_quorum, self.replication_quorum):
            if not 1 <= q <= self.nodes:
                raise Invalid(f"a quorum must be between 1 and {self.nodes}")

    def intersects(self) -> bool:
        return self.election_quorum + self.replication_quorum > self.nodes

    def commit_failures_tolerated(self) -> int:
        return self.nodes - self.replication_quorum

    def election_failures_tolerated(self) -> int:
        return self.nodes - self.election_quorum

    def validate(self) -> str:
        if not self.intersects():
            raise Invalid(
                f"Q1={self.election_quorum} + Q2={self.replication_quorum} <= "
                f"N={self.nodes}; the quorums do not intersect, a new leader "
                "could miss a committed entry, unsafe"
            )
        return (
            f"safe: Q1 {self.election_quorum} + Q2 {self.replication_quorum} > "
            f"N {self.nodes}; commits tolerate "
            f"{self.commit_failures_tolerated()} failure(s), elections "
            f"{self.election_failures_tolerated()}, the speed-for-availability "
            "trade the majority rule hides"
        )
