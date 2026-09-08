from __future__ import annotations

import pytest

from relay.controlledshutdown import ControlledShutdown
from relay.errors import Invalid


class TestPlan:
    def test_leadership_moves_to_the_highest_in_sync_replica(self):
        cs = ControlledShutdown(broker="b1")
        cs.led_by_broker("t-0", {"b1": 100, "b2": 100, "b3": 90})
        moves = cs.plan()
        assert moves["t-0"] == "b2"

    def test_each_led_partition_gets_a_move(self):
        cs = ControlledShutdown(broker="b1")
        cs.led_by_broker("t-0", {"b1": 50, "b2": 50})
        cs.led_by_broker("t-1", {"b1": 70, "b3": 70})
        moves = cs.plan()
        assert set(moves) == {"t-0", "t-1"}

    def test_the_shutting_broker_is_never_its_own_target(self):
        cs = ControlledShutdown(broker="b1")
        cs.led_by_broker("t-0", {"b1": 100, "b2": 80})
        assert cs.plan()["t-0"] != "b1"


class TestBlocked:
    def test_a_sole_in_sync_partition_is_blocked(self):
        cs = ControlledShutdown(broker="b1")
        cs.led_by_broker("t-0", {"b1": 100})  # only b1 is in sync
        assert cs.blocked() == ["t-0"]
        assert not cs.is_clean()

    def test_a_shutdown_with_targets_everywhere_is_clean(self):
        cs = ControlledShutdown(broker="b1")
        cs.led_by_broker("t-0", {"b1": 100, "b2": 100})
        cs.led_by_broker("t-1", {"b1": 50, "b3": 50})
        assert cs.is_clean()
        assert cs.blocked() == []

    def test_a_blocked_partition_still_reports_moves_for_the_others(self):
        cs = ControlledShutdown(broker="b1")
        cs.led_by_broker("safe", {"b1": 10, "b2": 10})
        cs.led_by_broker("stuck", {"b1": 10})
        assert "safe" in cs.plan()
        assert cs.blocked() == ["stuck"]


class TestRefusal:
    def test_a_partition_the_broker_is_not_in_sync_for_is_refused(self):
        cs = ControlledShutdown(broker="b1")
        with pytest.raises(Invalid) as caught:
            cs.led_by_broker("t-0", {"b2": 100, "b3": 100})
        assert "not in the in-sync set" in str(caught.value)


class TestNote:
    def test_the_note_flags_blocked_partitions(self):
        cs = ControlledShutdown(broker="b1")
        cs.led_by_broker("stuck", {"b1": 10})
        assert "blocked" in cs.note()

    def test_a_clean_note_reports_no_gap(self):
        cs = ControlledShutdown(broker="b1")
        cs.led_by_broker("t-0", {"b1": 10, "b2": 10})
        assert "none blocked" in cs.note()
