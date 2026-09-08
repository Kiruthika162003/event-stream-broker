from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.partitionplan import (
    PartitionRequirements,
    audit_count,
    explain_plan,
    plan_partitions,
)


def throughput_bound() -> PartitionRequirements:
    return PartitionRequirements(
        target_throughput=1000,
        per_partition_capacity=100,
        consumer_parallelism=6,
    )


def parallelism_bound() -> PartitionRequirements:
    return PartitionRequirements(
        target_throughput=200,
        per_partition_capacity=100,
        consumer_parallelism=16,
    )


class TestPlanning:
    def test_throughput_can_be_the_binding_floor(self):
        assert plan_partitions(throughput_bound()) == 12
        assert "bound by throughput" in explain_plan(throughput_bound())

    def test_parallelism_can_be_the_binding_floor(self):
        assert plan_partitions(parallelism_bound()) == 20
        assert "bound by consumer parallelism" in explain_plan(
            parallelism_bound()
        )

    def test_headroom_is_added_above_the_floor(self):
        assert plan_partitions(throughput_bound()) > 10

    def test_bad_requirements_are_refused(self):
        with pytest.raises(Invalid):
            PartitionRequirements(
                target_throughput=0,
                per_partition_capacity=100,
                consumer_parallelism=1,
            )


class TestAudit:
    def test_under_provisioning_is_refused_as_permanent(self):
        with pytest.raises(Invalid) as caught:
            audit_count(throughput_bound(), 5)
        assert "permanent under-provisioning" in str(caught.value)

    def test_a_well_matched_count_passes(self):
        assert "well matched" in audit_count(
            throughput_bound(), 12
        )

    def test_a_vast_over_count_is_the_other_mistake(self):
        verdict = audit_count(parallelism_bound(), 500)
        assert "the mistake in the other direction" in verdict
