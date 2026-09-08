"""Distributed rate limit: split a global cap across nodes, and mind the waste.

Enforcing a global rate limit, this client may produce a million
bytes a second across the whole cluster, is easy on one node and
hard across many, because the limit is global while each node
enforces locally. The simplest approach divides the limit evenly:
with N nodes each allows the limit over N. It is correct, the sum
never exceeds the global limit, but it wastes capacity when load is
uneven, because a node receiving most of the client's traffic hits
its one-Nth share and throttles while other nodes sit far under
theirs, so the client is throttled well below the global limit it
was promised. The waste is exactly the unused share on the idle
nodes, and it grows with how skewed the load is: perfectly balanced
load wastes nothing, all-on-one-node wastes nearly everything. A
better approach pools the unused share: nodes report their usage to
a shared counter and draw from the global limit rather than a fixed
slice, so a busy node can use the capacity idle nodes are not, at
the cost of the coordination the static split avoids. The model
computes, for a load distribution across nodes, how much the static
split throttles versus the true global limit, and the waste that
pooling would recover. It refuses a node count below one and a
negative limit, and reports the effective throughput the static
split allows against the global limit, because a client throttled
far under its global limit on a static split is one whose load is
skewed, the case pooling was invented for and static division
handles worst."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class DistributedRateLimit:
    global_limit: int
    nodes: int

    def __post_init__(self) -> None:
        if self.nodes < 1:
            raise Invalid("need at least one node")
        if self.global_limit < 0:
            raise Invalid("the limit cannot be negative")

    def static_share(self) -> float:
        return self.global_limit / self.nodes

    def static_effective(self, loads: list[float]) -> float:
        # each node is capped at its share; the client's total served is the
        # sum of min(load, share) across nodes
        share = self.static_share()
        return sum(min(load, share) for load in loads)

    def wasted(self, loads: list[float]) -> float:
        if sum(loads) < self.global_limit:
            return 0.0
        return self.global_limit - self.static_effective(loads)

    def report(self, loads: list[float]) -> str:
        effective = self.static_effective(loads)
        wasted = self.wasted(loads)
        return (
            f"static split serves {effective:.0f} of the {self.global_limit} "
            f"global limit; {wasted:.0f} wasted on idle nodes' shares, which "
            "pooling would recover, the skewed-load case static division "
            "handles worst"
        )
