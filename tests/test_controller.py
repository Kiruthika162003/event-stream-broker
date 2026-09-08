from __future__ import annotations

import contextlib

import pytest

from relay.controller import Controller, Metadata
from relay.errors import Fenced, Invalid


def controller() -> Controller:
    return Controller(
        controller_epoch=3,
        metadata=Metadata(version=10, leaders={0: "b1", 1: "b2"}),
    )


class TestUpdates:
    def test_a_leader_change_bumps_the_version(self):
        chosen = controller()
        verdict = chosen.update_leader(3, 0, "b3")
        assert "metadata version 11" in verdict
        assert chosen.metadata.leader_of(0) == "b3"

    def test_an_old_controller_epoch_is_fenced(self):
        chosen = controller()
        with pytest.raises(Fenced) as caught:
            chosen.update_leader(2, 0, "rogue")
        assert "cluster-level split brain" in str(caught.value)


class TestRouting:
    def test_a_current_broker_routes_correctly(self):
        assert controller().route(10, 1) == "b2"

    def test_a_stale_broker_is_told_to_refresh(self):
        chosen = controller()
        with pytest.raises(Invalid) as caught:
            chosen.route(9, 0)
        assert "route to a leader that moved" in str(caught.value)
        assert chosen.stale_routes_caught == 1

    def test_routing_an_unknown_partition_is_refused(self):
        with pytest.raises(Invalid):
            controller().route(10, 99)


class TestTheReport:
    def test_the_report_counts_updates_and_stale_catches(self):
        chosen = controller()
        chosen.update_leader(3, 0, "b3")
        with contextlib.suppress(Invalid):
            chosen.route(10, 0)
        report = chosen.report()
        assert "controller epoch 3" in report
        assert "1 update(s)" in report
        assert "before they reached a dead leader" in report
