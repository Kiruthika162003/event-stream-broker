from __future__ import annotations

import pytest

from relay.closestreplica import ReplicaLocation, select_closest
from relay.errors import Invalid


class TestSelection:
    def test_the_closest_in_sync_replica_wins(self):
        replicas = [
            ReplicaLocation("b1", "cross-region", in_sync=True),
            ReplicaLocation("b2", "same-rack", in_sync=True),
            ReplicaLocation("b3", "same-host", in_sync=True),
        ]
        chosen, note = select_closest(replicas)
        assert chosen.broker == "b3"
        assert "same-host" in note

    def test_distance_never_overrides_in_sync(self):
        replicas = [
            ReplicaLocation("near", "same-host", in_sync=False),
            ReplicaLocation("far", "cross-region", in_sync=True),
        ]
        chosen, note = select_closest(replicas)
        assert chosen.broker == "far"
        assert "pays for a replica's health problem" in note

    def test_no_in_sync_replica_is_refused(self):
        replicas = [
            ReplicaLocation("b1", "same-host", in_sync=False),
        ]
        with pytest.raises(Invalid) as caught:
            select_closest(replicas)
        assert "nothing correct to pick" in str(caught.value)

    def test_an_unknown_tier_is_refused(self):
        with pytest.raises(Invalid):
            ReplicaLocation("b", "same-galaxy", in_sync=True)


class TestReporting:
    def test_a_clean_pick_names_the_tier(self):
        replicas = [
            ReplicaLocation("b1", "same-rack", in_sync=True),
            ReplicaLocation("b2", "cross-region", in_sync=True),
        ]
        _, note = select_closest(replicas)
        assert "the closest in-sync copy" in note

    def test_ties_break_on_broker_name(self):
        replicas = [
            ReplicaLocation("b2", "same-rack", in_sync=True),
            ReplicaLocation("b1", "same-rack", in_sync=True),
        ]
        chosen, _ = select_closest(replicas)
        assert chosen.broker == "b1"
