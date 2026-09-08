from __future__ import annotations

import pytest

from relay.describequorum import QuorumStatus
from relay.errors import Invalid


def _q(offsets):
    return QuorumStatus(leader_offset=1000, voter_offsets=offsets, max_lag=100)


class TestCommit:
    def test_a_quorum_with_a_majority_caught_up_can_commit(self):
        q = _q({"v1": 1000, "v2": 990, "v3": 500})
        assert q.can_commit()

    def test_a_quorum_below_the_majority_cannot_commit(self):
        q = _q({"v1": 1000, "v2": 500, "v3": 400})
        assert not q.can_commit()

    def test_an_empty_quorum_is_refused(self):
        with pytest.raises(Invalid):
            QuorumStatus(leader_offset=1000, voter_offsets={})


class TestRisk:
    def test_exactly_the_majority_is_at_risk(self):
        # 5 voters, majority 3, exactly 3 caught up
        q = _q({"v1": 1000, "v2": 990, "v3": 950, "v4": 500, "v5": 400})
        assert q.at_risk()
        assert q.margin() == 0

    def test_a_comfortable_quorum_has_margin(self):
        q = _q({"v1": 1000, "v2": 990, "v3": 980})
        assert not q.at_risk()
        assert q.margin() == 1


class TestReport:
    def test_an_unhealthy_quorum_is_named(self):
        q = _q({"v1": 1000, "v2": 400, "v3": 300})
        assert "UNHEALTHY" in q.report()
        assert "outage in progress" in q.report()

    def test_an_at_risk_quorum_names_the_laggard(self):
        q = _q({"v1": 1000, "v2": 990, "v3": 950, "v4": 500, "v5": 400})
        note = q.report()
        assert "AT RISK" in note
        assert "most lagged 'v5'" in note
