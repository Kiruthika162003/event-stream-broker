from __future__ import annotations

import pytest

from relay.errors import Invalid, Missing
from relay.logdirfailure import LogDirFailure


def _broker() -> LogDirFailure:
    b = LogDirFailure()
    b.add_directory("/disk1")
    b.add_directory("/disk2")
    b.place("t-0", "/disk1")
    b.place("t-1", "/disk1")
    b.place("t-2", "/disk2")
    return b


class TestFailure:
    def test_failing_a_disk_takes_only_its_partitions_offline(self):
        b = _broker()
        offline = b.fail("/disk1")
        assert offline == ["t-0", "t-1"]
        assert b.offline_partitions() == ["t-0", "t-1"]

    def test_a_partition_on_a_healthy_disk_stays_serviceable(self):
        b = _broker()
        b.fail("/disk1")
        assert b.is_serviceable("t-2")
        assert not b.is_serviceable("t-0")

    def test_the_broker_stays_up_with_one_working_disk(self):
        b = _broker()
        b.fail("/disk1")
        assert not b.broker_down()

    def test_the_broker_is_down_only_when_all_disks_fail(self):
        b = _broker()
        b.fail("/disk1")
        b.fail("/disk2")
        assert b.broker_down()


class TestPlacement:
    def test_placing_on_a_failed_disk_is_refused(self):
        b = _broker()
        b.fail("/disk1")
        with pytest.raises(Invalid) as caught:
            b.place("t-3", "/disk1")
        assert "cannot land" in str(caught.value)

    def test_placing_on_an_unknown_disk_is_refused(self):
        b = _broker()
        with pytest.raises(Invalid):
            b.place("t-3", "/disk9")

    def test_an_unplaced_partition_has_no_serviceability(self):
        b = _broker()
        with pytest.raises(Missing):
            b.is_serviceable("ghost")


class TestNote:
    def test_the_note_states_the_blast_radius(self):
        b = _broker()
        b.fail("/disk1")
        note = b.note()
        assert "1 online" in note
        assert "2 partition(s) offline" in note
