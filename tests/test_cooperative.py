from __future__ import annotations

import pytest

from relay.cooperative import CooperativeRebalance
from relay.errors import Invalid


def rebalance() -> CooperativeRebalance:
    return CooperativeRebalance(
        current={"c1": {0, 1, 2, 3}, "c2": {4, 5, 6, 7}},
        target={"c1": {0, 1}, "c2": {4, 5}, "c3": {2, 3, 6, 7}},
    )


class TestRevokePhase:
    def test_only_moving_partitions_are_revoked(self):
        chosen = rebalance()
        to_revoke = chosen.to_revoke()
        assert to_revoke == {"c1": {2, 3}, "c2": {6, 7}}

    def test_revoke_leaves_retained_partitions_live(self):
        chosen = rebalance()
        chosen.revoke_phase()
        assert chosen.current["c1"] == {0, 1}
        assert chosen.current["c2"] == {4, 5}

    def test_revoke_reports_the_moved_count(self):
        chosen = rebalance()
        verdict = chosen.revoke_phase()
        assert "revoked 4 partition(s)" in verdict
        assert "never paused" in verdict


class TestAssignPhase:
    def test_assign_completes_the_target(self):
        chosen = rebalance()
        chosen.revoke_phase()
        verdict = chosen.assign_phase()
        assert "no partition was ever owned by two" in verdict
        assert chosen.current["c3"] == {2, 3, 6, 7}

    def test_assign_before_revoke_is_refused(self):
        with pytest.raises(Invalid):
            rebalance().assign_phase()

    def test_double_revoke_is_refused(self):
        chosen = rebalance()
        chosen.revoke_phase()
        with pytest.raises(Invalid):
            chosen.revoke_phase()


class TestSafety:
    def test_no_partition_is_double_owned_after(self):
        chosen = rebalance()
        chosen.revoke_phase()
        chosen.assign_phase()
        assert chosen.never_double_owned()

    def test_the_final_assignment_matches_target(self):
        chosen = rebalance()
        chosen.revoke_phase()
        chosen.assign_phase()
        assert chosen.current == chosen.target
