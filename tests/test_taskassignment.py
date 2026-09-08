from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.taskassignment import TaskAssignment


def _ta():
    return TaskAssignment(instances=["i1", "i2", "i3"])


class TestActive:
    def test_active_tasks_are_assigned(self):
        t = _ta()
        t.assign_active("task-0", "i1")
        assert t.active["task-0"] == "i1"

    def test_an_unknown_instance_is_refused(self):
        t = _ta()
        with pytest.raises(Invalid):
            t.assign_active("task-0", "ghost")


class TestStandby:
    def test_a_standby_on_another_instance_is_placed(self):
        t = _ta()
        t.assign_active("task-0", "i1")
        assert "placed on 'i2'" in t.assign_standby("task-0", "i2")

    def test_a_standby_on_the_actives_instance_is_refused(self):
        t = _ta()
        t.assign_active("task-0", "i1")
        with pytest.raises(Invalid) as caught:
            t.assign_standby("task-0", "i1")
        assert "takes it too" in str(caught.value)

    def test_a_standby_with_one_instance_is_refused(self):
        t = TaskAssignment(instances=["only"])
        t.assign_active("task-0", "only")
        with pytest.raises(Invalid) as caught:
            t.assign_standby("task-0", "only")
        assert "only one instance" in str(caught.value)


class TestImbalance:
    def test_imbalance_is_the_busiest_minus_idlest(self):
        t = _ta()
        t.assign_active("a", "i1")
        t.assign_active("b", "i1")
        t.assign_active("c", "i2")
        assert t.imbalance() == 2  # i1=2, i3=0


class TestReport:
    def test_a_clean_assignment_reports_no_collocation(self):
        t = _ta()
        t.assign_active("a", "i1")
        t.assign_standby("a", "i2")
        assert "off its active's instance" in t.report()
