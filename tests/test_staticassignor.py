from __future__ import annotations

import pytest

from relay.errors import Invalid, Missing
from relay.staticassignor import StaticAssignor


def _assignor() -> StaticAssignor:
    a = StaticAssignor()
    a.assign("t-0", "m1")
    a.assign("t-1", "m1")
    a.assign("t-2", "m2")
    return a


class TestAssign:
    def test_a_member_gets_its_configured_partitions(self):
        a = _assignor()
        assert a.partitions_for("m1") == ["t-0", "t-1"]

    def test_the_owner_of_a_partition_is_returned(self):
        a = _assignor()
        assert a.owner("t-2") == "m2"

    def test_reassigning_to_the_same_member_is_idempotent(self):
        a = _assignor()
        a.assign("t-0", "m1")  # no change
        assert a.owner("t-0") == "m1"

    def test_assigning_one_partition_to_two_members_is_refused(self):
        a = _assignor()
        with pytest.raises(Invalid) as caught:
            a.assign("t-0", "m2")
        assert "double-consumption" in str(caught.value)


class TestPresence:
    def test_a_present_members_partitions_are_consumed(self):
        a = _assignor()
        a.mark_present("m1")
        a.mark_present("m2")
        assert a.unconsumed() == []

    def test_an_absent_members_partitions_go_unconsumed(self):
        a = _assignor()
        a.mark_present("m1")
        # m2 never marked present; t-2 has no consumer
        assert a.unconsumed() == ["t-2"]

    def test_a_departed_member_leaves_its_partitions_unconsumed(self):
        a = _assignor()
        a.mark_present("m1")
        a.mark_present("m2")
        a.mark_present("m1", present=False)  # rolling restart, m1 down
        assert a.unconsumed() == ["t-0", "t-1"]


class TestRefusal:
    def test_an_unmapped_partition_lookup_is_missing(self):
        a = _assignor()
        with pytest.raises(Missing):
            a.owner("t-9")


class TestNote:
    def test_the_note_lists_unconsumed_partitions(self):
        a = _assignor()
        a.mark_present("m1")
        assert "unconsumed: ['t-2']" in a.note()
