from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.partitionreassigncancel import ReassignmentCancel


class TestCancel:
    def test_cancel_drops_the_target_only_replicas(self):
        r = ReassignmentCancel(original=["b1", "b2"], target=["b2", "b3"])
        dropped = r.cancel()
        assert dropped == ["b3"]  # b2 was already an original

    def test_reverting_restores_the_original_set(self):
        r = ReassignmentCancel(original=["b1", "b2"], target=["b3", "b4"])
        assert r.reverted_replicas() == ["b1", "b2"]

    def test_the_in_flight_union_holds_both_sets(self):
        r = ReassignmentCancel(original=["b1", "b2"], target=["b2", "b3"])
        assert r.in_flight_union() == ["b1", "b2", "b3"]


class TestRefusals:
    def test_cancel_with_no_surviving_original_is_refused(self):
        # both originals removed from the cluster; only a target survives
        r = ReassignmentCancel(
            original=["b1", "b2"], target=["b3"], surviving={"b3"}
        )
        with pytest.raises(Invalid) as caught:
            r.cancel()
        assert "undefined state" in str(caught.value)

    def test_cancel_of_a_completed_reassignment_is_refused(self):
        r = ReassignmentCancel(
            original=["b1"], target=["b2"], completed=True
        )
        with pytest.raises(Invalid) as caught:
            r.cancel()
        assert "already completed" in str(caught.value)


class TestSurviving:
    def test_a_partial_survival_still_allows_cancel(self):
        # b1 removed but b2 survives, so leadership can go back to b2
        r = ReassignmentCancel(
            original=["b1", "b2"], target=["b3"], surviving={"b2", "b3"}
        )
        assert r.cancel() == ["b3"]


class TestNote:
    def test_the_note_names_the_dropped_replicas(self):
        r = ReassignmentCancel(original=["b1"], target=["b2"])
        assert "dropping ['b2']" in r.note()

    def test_a_completed_note_says_nothing_to_cancel(self):
        r = ReassignmentCancel(original=["b1"], target=["b2"], completed=True)
        assert "nothing in flight" in r.note()
