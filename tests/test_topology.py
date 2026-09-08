from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.topology import Topology


def _line():
    t = Topology()
    for n in ("source", "map", "filter", "sink"):
        t.add_node(n)
    t.connect("source", "map")
    t.connect("map", "filter")
    t.connect("filter", "sink")
    return t


class TestValidate:
    def test_a_dag_validates(self):
        assert "valid DAG" in _line().validate()

    def test_a_cycle_is_rejected_with_its_path(self):
        t = _line()
        t.connect("sink", "map")  # back edge
        with pytest.raises(Invalid) as caught:
            t.validate()
        assert "cycle" in str(caught.value)
        assert "map" in str(caught.value)

    def test_an_edge_to_an_unknown_node_is_refused(self):
        t = Topology()
        t.add_node("a")
        with pytest.raises(Invalid) as caught:
            t.connect("a", "ghost")
        assert "never added" in str(caught.value)


class TestDepth:
    def test_depth_is_the_longest_source_to_sink_path(self):
        assert _line().depth() == 4

    def test_a_branch_takes_the_longest(self):
        t = Topology()
        for n in ("s", "a", "b", "c", "sink"):
            t.add_node(n)
        t.connect("s", "a")
        t.connect("s", "b")
        t.connect("b", "c")
        t.connect("c", "sink")
        # s->b->c->sink is length 4, s->a is length 2
        assert t.depth() == 4
