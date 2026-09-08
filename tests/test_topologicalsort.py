from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.topologicalsort import TopologicalSort


def _graph():
    t = TopologicalSort()
    for n in ("source", "parse", "enrich", "sink"):
        t.add_node(n)
    t.add_dependency("parse", "source")
    t.add_dependency("enrich", "parse")
    t.add_dependency("sink", "enrich")
    return t


class TestOrder:
    def test_dependencies_come_before_dependents(self):
        order = _graph().order()
        assert order.index("source") < order.index("parse")
        assert order.index("parse") < order.index("enrich")
        assert order.index("enrich") < order.index("sink")

    def test_a_cycle_has_no_order(self):
        t = TopologicalSort()
        for n in ("a", "b"):
            t.add_node(n)
        t.add_dependency("a", "b")
        t.add_dependency("b", "a")
        with pytest.raises(Invalid) as caught:
            t.order()
        assert "form a cycle" in str(caught.value)

    def test_an_edge_to_an_unknown_node_is_refused(self):
        t = TopologicalSort()
        t.add_node("a")
        with pytest.raises(Invalid):
            t.add_dependency("a", "ghost")


class TestFrontier:
    def test_a_linear_graph_starts_with_one(self):
        assert _graph().initial_frontier() == 1
        assert "a pipeline that serializes" in _graph().report()

    def test_independent_nodes_start_together(self):
        t = TopologicalSort()
        for n in ("a", "b", "c", "sink"):
            t.add_node(n)
        t.add_dependency("sink", "a")
        t.add_dependency("sink", "b")
        t.add_dependency("sink", "c")
        assert t.initial_frontier() == 3
        assert "parallelizable" in t.report()
