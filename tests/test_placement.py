from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.placement import Placer


def three_racks() -> Placer:
    return Placer(
        brokers=["b1", "b2", "b3"],
        rack_of={"b1": "ra", "b2": "rb", "b3": "rc"},
        replication_factor=3,
    )


def two_racks() -> Placer:
    return Placer(
        brokers=["b1", "b2", "b3"],
        rack_of={"b1": "ra", "b2": "rb", "b3": "ra"},
        replication_factor=3,
    )


class TestBalance:
    def test_replicas_spread_evenly(self):
        placer = three_racks()
        assignment = placer.place(6)
        assert placer.balance_spread(assignment) == 0

    def test_factor_above_broker_count_is_refused(self):
        with pytest.raises(Invalid):
            Placer(["b1", "b2"], {"b1": "ra", "b2": "rb"}, 3)


class TestRackIsolation:
    def test_enough_racks_gives_perfect_isolation(self):
        placer = three_racks()
        assignment = placer.place(6)
        assert placer.rack_violations(assignment) == []

    def test_too_few_racks_forces_violations(self):
        placer = two_racks()
        assignment = placer.place(6)
        assert placer.rack_violations(assignment) == [0, 1, 2, 3, 4, 5]


class TestTheReport:
    def test_a_clean_placement_spans_racks(self):
        report = three_racks().report(6)
        assert "balance spread 0" in report
        assert "no rack failure takes a majority" in report

    def test_a_constrained_placement_names_the_spof(self):
        report = two_racks().report(6)
        assert "6 partition(s) share a rack" in report
        assert "surfaces only in the outage" in report
