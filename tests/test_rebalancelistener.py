from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.rebalancelistener import RebalanceListener


def listener() -> RebalanceListener:
    return RebalanceListener(owned={0, 1, 2})


class TestRevokeThenAssign:
    def test_the_ordered_flow_commits_before_release(self):
        listener_obj = listener()
        listener_obj.begin_revoke({1})
        verdict = listener_obj.commit_on_revoke(1, 500)
        assert "committed at 500 before release" in verdict
        listener_obj.complete_revoke({1})
        assert 1 not in listener_obj.owned

    def test_on_assign_takes_new_partitions(self):
        listener_obj = listener()
        verdict = listener_obj.on_assign({5, 6})
        assert "seek to committed and load state" in verdict
        assert {5, 6} <= listener_obj.owned


class TestTheRace:
    def test_a_commit_after_revoke_completes_is_the_race(self):
        listener_obj = listener()
        listener_obj.begin_revoke({1})
        listener_obj.complete_revoke({1})
        with pytest.raises(Invalid) as caught:
            listener_obj.commit_on_revoke(1, 500)
        assert "the exact race the ordered callbacks close" in str(
            caught.value
        )

    def test_revoking_unowned_partitions_is_refused(self):
        with pytest.raises(Invalid):
            listener().begin_revoke({9})


class TestFailures:
    def test_a_thrown_on_revoke_does_not_stall_the_group(self):
        listener_obj = listener()
        listener_obj.begin_revoke({1})
        verdict = listener_obj.revoke_threw()
        assert "the rebalance proceeds" in verdict
        assert "corrupts its output" in verdict
        assert listener_obj.revoke_failures == 1

    def test_a_commit_outside_revoke_is_refused(self):
        with pytest.raises(Invalid):
            listener().commit_on_revoke(1, 500)
