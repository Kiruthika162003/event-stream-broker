from __future__ import annotations

import pytest

from relay.capacityplan import CapacityPlan
from relay.errors import Invalid


def _plan(**over):
    base = {
        "bytes_per_second": 1_000_000,
        "retention_seconds": 86_400,
        "replication_factor": 3,
        "brokers": 6,
    }
    base.update(over)
    return CapacityPlan(**base)


class TestDisk:
    def test_one_copy_is_throughput_times_retention(self):
        assert _plan().one_copy_bytes() == 86_400_000_000

    def test_total_disk_multiplies_by_the_factor(self):
        assert _plan().total_disk_bytes() == 259_200_000_000

    def test_per_broker_divides_across_brokers(self):
        assert _plan().per_broker_disk_bytes() == 43_200_000_000


class TestNetwork:
    def test_replication_out_is_rate_times_factor_minus_one(self):
        assert _plan().replication_out_bytes_per_second() == 2_000_000

    def test_factor_one_has_no_replication_traffic(self):
        assert _plan(replication_factor=1).replication_out_bytes_per_second() == 0


class TestRefusals:
    def test_a_bad_factor_is_refused(self):
        with pytest.raises(Invalid):
            _plan(replication_factor=0)

    def test_a_non_positive_retention_is_refused(self):
        with pytest.raises(Invalid) as caught:
            _plan(retention_seconds=0)
        assert "hides the real need" in str(caught.value)


class TestReport:
    def test_the_report_states_per_broker_and_replication(self):
        note = _plan().report()
        assert "per broker" in note
        assert "saturates the" in note
