from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.replicationfactor import ReplicationPlan


class TestValidation:
    def test_a_factor_above_the_broker_count_is_refused(self):
        with pytest.raises(Invalid) as caught:
            ReplicationPlan(factor=4, broker_count=3)
        assert "not two copies" in str(caught.value)

    def test_a_factor_below_one_is_refused(self):
        with pytest.raises(Invalid):
            ReplicationPlan(factor=0, broker_count=3)

    def test_a_valid_factor_is_accepted(self):
        plan = ReplicationPlan(factor=3, broker_count=3)
        assert plan.factor == 3


class TestBrokerFaultTolerance:
    def test_tolerance_is_one_less_than_the_factor(self):
        assert ReplicationPlan(factor=3, broker_count=5).broker_fault_tolerance() == 2

    def test_factor_one_is_named_as_no_replication(self):
        note = ReplicationPlan(factor=1, broker_count=3).durability_note()
        assert "no replication" in note


class TestRackFaultTolerance:
    def test_one_rack_has_no_rack_tolerance(self):
        plan = ReplicationPlan(factor=3, broker_count=3, rack_count=1)
        assert "no rack-failure tolerance" in plan.rack_fault_tolerance()

    def test_three_copies_across_three_racks_survives_one_loss(self):
        plan = ReplicationPlan(factor=3, broker_count=6, rack_count=3)
        assert "survives losing 2 of 3 rack(s)" in plan.rack_fault_tolerance()

    def test_three_copies_across_two_racks_is_limited(self):
        plan = ReplicationPlan(factor=3, broker_count=4, rack_count=2)
        assert "the smaller rack at best" in plan.rack_fault_tolerance()
