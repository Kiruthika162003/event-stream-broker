from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.groupcoordinator import (
    CoordinatorLocator,
    coordinator_partition,
)


class TestPartitionHashing:
    def test_a_group_maps_to_a_deterministic_partition(self):
        assert coordinator_partition("billing", 50) == 36
        assert coordinator_partition("billing", 50) == 36

    def test_different_groups_spread(self):
        parts = {
            coordinator_partition(g, 50)
            for g in ("billing", "search", "fulfilment")
        }
        assert len(parts) == 3

    def test_zero_partitions_is_refused(self):
        with pytest.raises(Invalid):
            coordinator_partition("g", 0)


def locator() -> CoordinatorLocator:
    return CoordinatorLocator(
        offset_partitions=50,
        partition_leaders={36: "b3", 20: "b1", 14: "b2"},
    )


class TestLocating:
    def test_the_coordinator_is_the_offset_partition_leader(self):
        assert locator().coordinator_for("billing") == "b3"

    def test_a_leaderless_offset_partition_is_unavailable(self):
        loc = CoordinatorLocator(50, {})
        with pytest.raises(Invalid) as caught:
            loc.coordinator_for("billing")
        assert "coordination is unavailable" in str(caught.value)


class TestRedirect:
    def test_the_right_broker_serves(self):
        assert "b3 coordinates billing" in (
            locator().serve_or_redirect("billing", "b3")
        )

    def test_the_wrong_broker_redirects(self):
        with pytest.raises(Invalid) as caught:
            locator().serve_or_redirect("billing", "b1")
        assert "NOT_COORDINATOR" in str(caught.value)
        assert "decided without authority" in str(caught.value)


class TestFailover:
    def test_a_failover_moves_coordination_with_the_partition(self):
        loc = locator()
        verdict = loc.on_failover(36, "b5")
        assert "just a partition failover" in verdict
        assert loc.coordinator_for("billing") == "b5"
