from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.findcoordinator import CoordinatorMap


class TestPartitionFor:
    def test_the_mapping_is_stable_for_a_group_id(self):
        cmap = CoordinatorMap(
            offsets_partitions=50,
            leaders=dict.fromkeys(range(50), "b1"),
        )
        first = cmap.partition_for("orders-consumer")
        second = cmap.partition_for("orders-consumer")
        assert first == second
        assert 0 <= first < 50

    def test_a_zero_partition_offsets_topic_is_refused(self):
        with pytest.raises(Invalid):
            CoordinatorMap(offsets_partitions=0, leaders={})


class TestCoordinatorFor:
    def test_the_coordinator_is_the_partition_leader(self):
        cmap = CoordinatorMap(
            offsets_partitions=4,
            leaders={0: "b0", 1: "b1", 2: "b2", 3: "b3"},
        )
        part = cmap.partition_for("g")
        assert cmap.coordinator_for("g") == f"b{part}"

    def test_a_leaderless_partition_forces_a_retry(self):
        cmap = CoordinatorMap(
            offsets_partitions=1,
            leaders={0: None},
        )
        with pytest.raises(Invalid) as caught:
            cmap.coordinator_for("g")
        assert "must be" in str(caught.value)
        assert "retried" in str(caught.value)


class TestColocated:
    def test_a_single_partition_colocates_every_group(self):
        cmap = CoordinatorMap(offsets_partitions=1, leaders={0: "b0"})
        assert cmap.colocated("g1", "g2")
