from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.prevote import PreVote


class TestRequest:
    def test_a_peer_without_a_leader_grants(self):
        pv = PreVote(voters=3)
        assert pv.request("p1", heard_leader_recently=False, log_current=True)

    def test_a_peer_with_a_live_leader_refuses(self):
        pv = PreVote(voters=3)
        assert not pv.request("p1", heard_leader_recently=True, log_current=True)

    def test_a_stale_log_is_refused_the_pre_vote(self):
        pv = PreVote(voters=3)
        assert not pv.request("p1", heard_leader_recently=False, log_current=False)


class TestCampaign:
    def test_a_majority_pre_vote_warrants_a_campaign(self):
        pv = PreVote(voters=3)
        pv.request("p1", heard_leader_recently=False, log_current=True)
        pv.request("p2", heard_leader_recently=False, log_current=True)
        assert pv.warranted()
        assert "increment the term" in pv.campaign()

    def test_a_partitioned_node_stands_down(self):
        pv = PreVote(voters=5)
        # peers still have a leader, so no grants
        pv.request("p1", heard_leader_recently=True, log_current=True)
        with pytest.raises(Invalid) as caught:
            pv.campaign()
        assert "stands down without bumping its term" in str(caught.value)


class TestReport:
    def test_a_warranted_campaign_is_named(self):
        pv = PreVote(voters=3)
        pv.request("p1", heard_leader_recently=False, log_current=True)
        pv.request("p2", heard_leader_recently=False, log_current=True)
        assert "campaign warranted" in pv.report()

    def test_a_stand_down_is_named(self):
        pv = PreVote(voters=3)
        assert "stand down" in pv.report()


class TestConfig:
    def test_zero_voters_is_refused(self):
        with pytest.raises(Invalid):
            PreVote(voters=0)
