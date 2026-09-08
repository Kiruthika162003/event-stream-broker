from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.logdirs import LogDirBalancer


def balancer() -> LogDirBalancer:
    return LogDirBalancer(disks=["d1", "d2", "d3"])


class TestPlacement:
    def test_partitions_spread_by_bytes(self):
        b = balancer()
        b.place(0, size=1000)
        b.place(1, size=10)
        b.place(2, size=10)
        # partition 1 and 2 should avoid d1 which holds the big one
        assert b.partition_disk[1] != b.partition_disk[0]

    def test_a_disk_per_partition_not_striped(self):
        b = balancer()
        b.place(0, size=100)
        # a partition lives on exactly one disk
        assert b.partition_disk[0] in b.disks

    def test_no_disks_is_refused(self):
        with pytest.raises(Invalid):
            LogDirBalancer(disks=[])


class TestFailure:
    def test_a_disk_failure_strands_only_its_partitions(self):
        b = balancer()
        b.partition_disk = {0: "d1", 1: "d1", 2: "d2"}
        verdict = b.fail_disk("d1")
        assert "[0, 1] offline" in verdict
        assert "the broker stays alive" in verdict
        assert "bounded blast radius" in verdict

    def test_placement_avoids_a_failed_disk(self):
        b = balancer()
        b.fail_disk("d1")
        b.place(0, size=100)
        assert b.partition_disk[0] != "d1"

    def test_an_unknown_disk_cannot_fail(self):
        with pytest.raises(Invalid):
            balancer().fail_disk("d9")


class TestRelocation:
    def test_a_sole_replica_is_not_risked_in_transit(self):
        b = balancer()
        b.place(0, size=100)
        with pytest.raises(Invalid) as caught:
            b.relocate(0, sole_replica=True)
        assert "named rather than risked" in str(caught.value)

    def test_a_replicated_partition_relocates(self):
        b = balancer()
        b.place(0, size=100)
        assert "relocated to balance bytes" in b.relocate(
            0, sole_replica=False
        )
