from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.gracefulshutdown import ShutdownPlan, validate_handoff


def plan(**overrides) -> ShutdownPlan:
    settings = {
        "departing": "b1",
        "led_partitions": {0: ["b1", "b2", "b3"], 1: ["b1", "b2"]},
        "caught_up": {0: {"b2"}, 1: {"b2"}},
    }
    settings.update(overrides)
    return ShutdownPlan(**settings)


class TestHandoff:
    def test_leadership_moves_to_a_caught_up_follower(self):
        p = plan()
        p.execute()
        assert p.handed_off == {0: "b2", 1: "b2"}
        assert p.may_exit()

    def test_a_clean_shutdown_needs_no_election(self):
        report = plan().execute()
        assert "handed off, no election needed" in report
        assert "no partition left leaderless" in report


class TestStranding:
    def test_a_partition_with_no_caught_up_follower_strands(self):
        p = plan(caught_up={0: {"b2"}, 1: set()})
        p.execute()
        assert p.stranded == [1]
        assert not p.may_exit()

    def test_stranding_is_reported_not_hidden(self):
        report = plan(caught_up={0: set(), 1: set()}).execute()
        assert "stranded with no caught-up follower" in report
        assert "not pretended away" in report


class TestValidation:
    def test_handing_off_to_a_laggard_is_refused(self):
        with pytest.raises(Invalid) as caught:
            validate_handoff(0, "b3", caught_up={"b2"})
        assert "turns graceful shutdown into data loss" in str(
            caught.value
        )

    def test_handing_off_to_a_caught_up_replica_is_fine(self):
        validate_handoff(0, "b2", caught_up={"b2"})
