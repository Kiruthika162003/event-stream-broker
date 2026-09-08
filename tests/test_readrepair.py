from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.readrepair import ReadRepair, ReplicaValue


class TestResolve:
    def test_the_newest_version_is_the_answer(self):
        rr = ReadRepair()
        value, behind = rr.resolve([
            ReplicaValue("r1", "old", 1),
            ReplicaValue("r2", "new", 3),
            ReplicaValue("r3", "old", 1),
        ])
        assert value == "new"
        assert set(behind) == {"r1", "r3"}

    def test_all_agreeing_repairs_nothing(self):
        rr = ReadRepair()
        _value, behind = rr.resolve([
            ReplicaValue("r1", "v", 5),
            ReplicaValue("r2", "v", 5),
        ])
        assert behind == []

    def test_no_replicas_is_refused(self):
        with pytest.raises(Invalid):
            ReadRepair().resolve([])


class TestReport:
    def test_it_reports_repaired_replicas(self):
        rr = ReadRepair()
        note = rr.report([
            ReplicaValue("r1", "old", 1),
            ReplicaValue("r2", "new", 3),
        ])
        assert "repaired 1/2 replica(s)" in note

    def test_agreement_reports_nothing_to_repair(self):
        rr = ReadRepair()
        note = rr.report([ReplicaValue("r1", "v", 1), ReplicaValue("r2", "v", 1)])
        assert "nothing to repair" in note


class TestConflict:
    def test_concurrent_versions_are_a_conflict(self):
        rr = ReadRepair()
        assert rr.concurrent_conflict([(2, 1), (1, 2)])

    def test_ordered_versions_are_not(self):
        rr = ReadRepair()
        assert not rr.concurrent_conflict([(1, 1), (2, 1)])
