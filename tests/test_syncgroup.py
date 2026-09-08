from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.syncgroup import SyncPhase


def _phase():
    return SyncPhase(leader="c1", members={"c1", "c2"})


class TestSubmit:
    def test_the_leader_submits_a_covering_plan(self):
        s = _phase()
        note = s.submit("c1", {"c1": [0, 1], "c2": [2, 3]})
        assert "leader c1 submitted a plan for 2 member(s)" in note

    def test_a_follower_cannot_submit(self):
        s = _phase()
        with pytest.raises(Invalid) as caught:
            s.submit("c2", {"c1": [0], "c2": [1]})
        assert "non-leader submission is refused" in str(caught.value)

    def test_a_plan_missing_a_member_is_refused(self):
        s = _phase()
        with pytest.raises(Invalid) as caught:
            s.submit("c1", {"c1": [0, 1, 2, 3]})
        assert "cover exactly the members" in str(caught.value)

    def test_a_double_owned_partition_is_refused(self):
        s = _phase()
        with pytest.raises(Invalid) as caught:
            s.submit("c1", {"c1": [0, 1], "c2": [1, 2]})
        assert "processes every record twice" in str(caught.value)


class TestSliceFor:
    def test_each_member_gets_only_its_own_slice(self):
        s = _phase()
        s.submit("c1", {"c1": [0, 1], "c2": [2, 3]})
        assert s.slice_for("c2") == [2, 3]

    def test_a_follower_before_submit_waits(self):
        s = _phase()
        with pytest.raises(Invalid) as caught:
            s.slice_for("c2")
        assert "the follower waits" in str(caught.value)


class TestShares:
    def test_shares_report_the_spread(self):
        s = _phase()
        s.submit("c1", {"c1": [0, 1], "c2": [2, 3]})
        note = s.shares()
        assert "spread 0" in note
