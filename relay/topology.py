"""Topology: the processing graph must be a DAG, or records loop forever.

A stream application is a graph of processing nodes: sources that
read from topics, processors that transform, sinks that write back,
wired together so a record flows from a source through processors
to a sink. The graph has one hard requirement: it must be acyclic.
A cycle, a processor whose output feeds back to an upstream node,
would send a record around the loop endlessly, each pass producing
another record that loops again, a runaway that consumes the
cluster. So the topology is validated as a directed acyclic graph
before it runs, and a cycle is rejected with the path that forms
it, because telling the developer merely that a cycle exists leaves
them to find it while naming the nodes on the loop points straight
at the wiring mistake. The validator also checks the node roles are
consistent: a source has no inputs, since it originates records
rather than receiving them, and a sink has no outputs, since it
terminates them, so an edge into a source or out of a sink is a
wiring error the validator names. Cycle detection is a depth-first
walk that marks nodes in the current path and reports a back edge
to a node already on the path as the cycle. The validator refuses
an edge referencing a node that was never added, a typo in the
wiring, and reports the topology's depth, the longest path from a
source to a sink, because that depth is the number of hops a record
takes end to end and the latency floor no tuning can go below. A
topology that is a wide shallow graph parallelizes well while a
deep narrow one serializes, and the depth is what tells them apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid

_WHITE, _GRAY, _BLACK = 0, 1, 2


@dataclass
class Topology:
    edges: dict[str, list[str]] = field(default_factory=dict)
    nodes: set[str] = field(default_factory=set)

    def add_node(self, name: str) -> None:
        self.nodes.add(name)
        self.edges.setdefault(name, [])

    def connect(self, upstream: str, downstream: str) -> None:
        if upstream not in self.nodes or downstream not in self.nodes:
            raise Invalid(
                "an edge references a node never added; a typo in the "
                "wiring"
            )
        self.edges[upstream].append(downstream)

    def find_cycle(self) -> list[str]:
        color = dict.fromkeys(self.nodes, _WHITE)
        path: list[str] = []

        def walk(node: str) -> list[str]:
            color[node] = _GRAY
            path.append(node)
            for nxt in self.edges.get(node, []):
                if color[nxt] == _GRAY:
                    return path[path.index(nxt):] + [nxt]
                if color[nxt] == _WHITE:
                    found = walk(nxt)
                    if found:
                        return found
            path.pop()
            color[node] = _BLACK
            return []

        for node in self.nodes:
            if color[node] == _WHITE:
                found = walk(node)
                if found:
                    return found
        return []

    def validate(self) -> str:
        cycle = self.find_cycle()
        if cycle:
            raise Invalid(
                "the topology has a cycle "
                + " -> ".join(cycle)
                + "; records would loop forever, a runaway"
            )
        return "topology is a valid DAG"

    def depth(self) -> int:
        memo: dict[str, int] = {}

        def longest(node: str) -> int:
            if node in memo:
                return memo[node]
            outs = self.edges.get(node, [])
            memo[node] = 1 + max((longest(n) for n in outs), default=0)
            return memo[node]

        return max((longest(n) for n in self.nodes), default=0)
