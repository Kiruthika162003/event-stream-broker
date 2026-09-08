from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.fetchmaxbytes import PerPartitionCap


def cap() -> PerPartitionCap:
    return PerPartitionCap(per_partition_max=100)


class TestAllocation:
    def test_data_under_the_cap_all_fits(self):
        allotted, note = cap().allocate(0, available=60, largest_record=10)
        assert allotted == 60
        assert "all 60 fit under the cap" in note

    def test_a_hot_partition_is_capped(self):
        allotted, note = cap().allocate(0, available=500, largest_record=10)
        assert allotted == 100
        assert "capped at 100 of 500" in note
        assert "needs its own consumer" in note

    def test_an_empty_partition_gets_nothing(self):
        allotted, note = cap().allocate(0, available=0, largest_record=0)
        assert allotted == 0
        assert "nothing available" in note


class TestOversizedRecord:
    def test_a_record_over_the_cap_is_returned_alone(self):
        allotted, note = cap().allocate(0, available=500, largest_record=200)
        assert allotted == 200
        assert "does not starve forever" in note


class TestRefusals:
    def test_a_zero_cap_is_refused(self):
        with pytest.raises(Invalid):
            PerPartitionCap(per_partition_max=0)
