from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.manualassign import ASSIGNED, SUBSCRIBED, AssignmentMode


class TestSubscribe:
    def test_subscribe_sets_the_mode(self):
        a = AssignmentMode()
        assert "coordinator assigns" in a.subscribe(["orders"])
        assert a.mode == SUBSCRIBED

    def test_subscribe_after_assign_is_refused(self):
        a = AssignmentMode()
        a.assign(["t-0"])
        with pytest.raises(Invalid) as caught:
            a.subscribe(["orders"])
        assert "both own the partition set" in str(caught.value)


class TestAssign:
    def test_assign_takes_specific_partitions(self):
        a = AssignmentMode()
        note = a.assign(["t-0", "t-1"])
        assert "no automatic failover" in note
        assert a.mode == ASSIGNED
        assert a.partitions == {"t-0", "t-1"}

    def test_assign_after_subscribe_is_refused(self):
        a = AssignmentMode()
        a.subscribe(["orders"])
        with pytest.raises(Invalid) as caught:
            a.assign(["t-0"])
        assert "different owners" in str(caught.value)

    def test_an_empty_assignment_is_refused(self):
        with pytest.raises(Invalid):
            AssignmentMode().assign([])


class TestFailover:
    def test_subscribed_has_automatic_failover(self):
        a = AssignmentMode()
        a.subscribe(["orders"])
        assert "coordinator moves partitions" in a.failover_note()

    def test_assigned_has_no_failover(self):
        a = AssignmentMode()
        a.assign(["t-0"])
        assert "operator owns that failover" in a.failover_note()

    def test_unset_has_no_partitions(self):
        assert "neither subscribed nor assigned" in AssignmentMode().failover_note()
