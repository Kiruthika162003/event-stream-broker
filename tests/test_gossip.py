from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.gossip import GossipModel


class TestConvergence:
    def test_a_single_node_needs_no_rounds(self):
        assert GossipModel(nodes=1, fanout=2).rounds_to_converge() == 0

    def test_convergence_is_logarithmic(self):
        # 1000 nodes, fanout 2 -> log3(1000) ~ 6-7 rounds
        rounds = GossipModel(nodes=1000, fanout=2).rounds_to_converge()
        assert rounds <= 7

    def test_a_higher_fanout_converges_faster(self):
        low = GossipModel(nodes=1000, fanout=2).rounds_to_converge()
        high = GossipModel(nodes=1000, fanout=10).rounds_to_converge()
        assert high < low


class TestMessages:
    def test_more_messages_at_higher_fanout(self):
        low = GossipModel(nodes=100, fanout=2).messages()
        high = GossipModel(nodes=100, fanout=20).messages()
        assert high > low


class TestConfig:
    def test_a_zero_fanout_is_refused(self):
        with pytest.raises(Invalid):
            GossipModel(nodes=10, fanout=0)

    def test_zero_nodes_is_refused(self):
        with pytest.raises(Invalid):
            GossipModel(nodes=0, fanout=2)


class TestReport:
    def test_report_names_rounds_and_messages(self):
        note = GossipModel(nodes=100, fanout=3).report()
        assert "converge in" in note
        assert "message(s)" in note
