"""Topological sort: an order where every dependency comes before its dependent.

Starting the nodes of a processing graph, or the sub-tasks of a
stream topology, in a valid order means every node runs only after
the ones it depends on, and a topological sort produces exactly such
an order from the dependency edges. The method here is Kahn's: find
the nodes with no remaining dependencies, emit one, remove its
outgoing edges which may free its dependents, and repeat, so a node
is emitted only once everything it needed has already been emitted.
The order is not unique, several valid orders exist when nodes are
independent, and any of them is correct because the only constraint
is the dependency edges. The sort also detects the one case with no
valid order: a cycle. If nodes remain but none has zero remaining
dependencies, they depend on each other in a loop, and no order can
put each after the others, so the sort reports the cycle rather than
emitting a partial order that would start a node before its
dependency. This is the same impossibility a stream topology's cycle
check catches, seen from the ordering side: a graph with a cycle
cannot be scheduled at all. The sorter takes nodes and their
dependency edges, returns a valid order, and refuses a graph with a
cycle, naming that the remaining nodes form one. It refuses an edge
referencing an unknown node, a wiring error, and reports how many
independent nodes could start first, the width of the initial
frontier, because a graph that starts with one node and then
serializes is a pipeline while one starting many is parallelizable,
and the frontier width tells them apart before the order is even
consumed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class TopologicalSort:
    nodes: set[str] = field(default_factory=set)
    deps: dict[str, set[str]] = field(default_factory=dict)

    def add_node(self, name: str) -> None:
        self.nodes.add(name)
        self.deps.setdefault(name, set())

    def add_dependency(self, node: str, depends_on: str) -> None:
        if node not in self.nodes or depends_on not in self.nodes:
            raise Invalid("a dependency references a node never added")
        self.deps[node].add(depends_on)

    def order(self) -> list[str]:
        remaining = {n: set(d) for n, d in self.deps.items()}
        out: list[str] = []
        while remaining:
            ready = sorted(n for n, d in remaining.items() if not d)
            if not ready:
                raise Invalid(
                    f"nodes {sorted(remaining)} form a cycle; no order can put "
                    "each after the others, the graph cannot be scheduled"
                )
            for n in ready:
                out.append(n)
                del remaining[n]
                for d in remaining.values():
                    d.discard(n)
        return out

    def initial_frontier(self) -> int:
        return sum(1 for d in self.deps.values() if not d)

    def report(self) -> str:
        width = self.initial_frontier()
        if width <= 1:
            return f"{width} node(s) start first; a pipeline that serializes"
        return f"{width} node(s) start first; parallelizable across them"
