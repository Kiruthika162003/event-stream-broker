"""Gossip: a fact reaches every node in a logarithmic number of rounds.

Disseminating a piece of information, a metadata change, a
membership update, to every node in a cluster can be done by having
a central coordinator tell each node, which is simple and fragile:
the coordinator is a bottleneck and a single point of failure.
Gossip does it without a coordinator: each round, every node that
knows the fact tells a few random peers, and those peers tell more,
so the fact spreads epidemically. The number of knowers roughly
multiplies each round, by one plus the fanout, the peers each node
tells, so it takes only a logarithmic number of rounds to reach all
N nodes, the same shape as a doubling that fills a cluster of
thousands in a handful of rounds. This is why gossip scales where a
coordinator does not: no node carries more than a fanout's worth of
messages per round, and there is no single point whose failure
stops dissemination, because the fact is spreading from everyone who
has it. The tradeoff is redundancy: gossip sends a fact to nodes
that may already have it, so it uses more total messages than a
perfect tree would, trading message efficiency for robustness and
simplicity, and the fanout tunes it, a higher fanout converging in
fewer rounds at the cost of more duplicate messages per round. The
estimator computes the rounds to full dissemination from the node
count and fanout, and the messages that costs, so an operator sizing
a gossip interval knows how long a change takes to reach everyone
and how much traffic it generates. It refuses a fanout below one,
which spreads to no one and never converges, and a node count below
one. It reports the rounds and the message overhead, because a
fanout chosen for fast convergence can generate far more messages
than the cluster needs, the redundancy gossip trades for robustness
made visible."
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class GossipModel:
    nodes: int
    fanout: int

    def __post_init__(self) -> None:
        if self.nodes < 1:
            raise Invalid("need at least one node")
        if self.fanout < 1:
            raise Invalid("a fanout below one spreads to no one and never converges")

    def rounds_to_converge(self) -> int:
        if self.nodes == 1:
            return 0
        # knowers multiply by ~(1 + fanout) per round until they reach N
        return math.ceil(math.log(self.nodes) / math.log(1 + self.fanout))

    def messages(self) -> int:
        # each round every knower sends `fanout` messages; a rough upper
        # bound is nodes * fanout * rounds when saturated
        return self.nodes * self.fanout * self.rounds_to_converge()

    def report(self) -> str:
        rounds = self.rounds_to_converge()
        return (
            f"{self.nodes} node(s) converge in ~{rounds} round(s) at fanout "
            f"{self.fanout}, ~{self.messages()} message(s); a higher fanout "
            "converges faster but sends more duplicates, the redundancy "
            "gossip trades for robustness"
        )
