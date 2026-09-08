from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.reassignprogress import ReassignmentTracker


class TestAdvancing:
    def test_a_closing_gap_gives_an_eta(self):
        t = ReassignmentTracker(target_offset=1000)
        t.observe(0, replica_offset=400, leader_offset=1000)
        t.observe(100, replica_offset=800, leader_offset=1000)
        verdict = t.eta()
        assert "advancing" in verdict
        assert "200 record(s) left" in verdict
        assert "patience, not intervention" in verdict

    def test_a_caught_up_replica_is_complete(self):
        t = ReassignmentTracker(target_offset=1000)
        t.observe(0, replica_offset=400, leader_offset=1000)
        t.observe(100, replica_offset=1000, leader_offset=1000)
        assert "complete" in t.eta()


class TestWedged:
    def test_a_flat_replica_is_wedged(self):
        t = ReassignmentTracker(target_offset=1000)
        t.observe(0, replica_offset=400, leader_offset=1000)
        t.observe(100, replica_offset=400, leader_offset=1200)
        verdict = t.eta()
        assert "WEDGED" in verdict
        assert "can never complete" in verdict

    def test_a_replica_losing_ground_is_wedged(self):
        t = ReassignmentTracker(target_offset=1000)
        t.observe(0, replica_offset=400, leader_offset=1000)
        t.observe(100, replica_offset=380, leader_offset=1400)
        assert "WEDGED" in t.eta()


class TestRefusals:
    def test_a_single_sample_has_no_eta(self):
        t = ReassignmentTracker(target_offset=1000)
        t.observe(0, replica_offset=400, leader_offset=1000)
        with pytest.raises(Invalid) as caught:
            t.eta()
        assert "worse than none" in str(caught.value)

    def test_time_must_advance(self):
        t = ReassignmentTracker(target_offset=1000)
        t.observe(10, 100, 1000)
        with pytest.raises(Invalid):
            t.observe(5, 200, 1000)
