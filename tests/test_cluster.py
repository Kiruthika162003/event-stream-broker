from __future__ import annotations

import pytest

from relay.cluster import ClusterMembership
from relay.errors import Invalid, Missing


def cluster() -> ClusterMembership:
    built = ClusterMembership(fence_after=30)
    built.register("b1", "rack-a", now=0)
    built.register("b2", "rack-b", now=0)
    built.register("b3", "rack-a", now=0)
    return built


class TestMembership:
    def test_registration_bumps_the_epoch(self):
        built = ClusterMembership(fence_after=30)
        assert "epoch 1" in built.register("b1", "rack-a", 0)
        assert "epoch 2" in built.register("b2", "rack-b", 0)

    def test_a_bad_fence_timeout_is_refused(self):
        with pytest.raises(Invalid):
            ClusterMembership(fence_after=0)

    def test_heartbeat_from_a_stranger_is_missing(self):
        with pytest.raises(Missing):
            cluster().heartbeat("ghost", now=5)


class TestFencing:
    def test_a_lapsed_broker_is_fenced(self):
        built = cluster()
        built.heartbeat("b1", now=25)
        built.heartbeat("b3", now=25)
        fenced = built.fence_lapsed(now=40)
        assert fenced == ["b2"]
        assert built.live_brokers() == ["b1", "b3"]

    def test_a_fenced_broker_must_re_register(self):
        built = cluster()
        built.fence_lapsed(now=100)
        with pytest.raises(Invalid) as caught:
            built.heartbeat("b1", now=101)
        assert "two views of it" in str(caught.value)

    def test_fencing_bumps_the_epoch(self):
        built = cluster()
        before = built.epoch
        built.fence_lapsed(now=100)
        assert built.epoch == before + 1


class TestRackDiversity:
    def test_enough_racks_can_span(self):
        verdict = cluster().rack_diverse_enough(2)
        assert "replicas can span racks" in verdict

    def test_too_few_racks_names_the_shared_switch(self):
        built = cluster()
        verdict = built.rack_diverse_enough(3)
        assert "some replicas must share a rack" in verdict
        assert "outage waiting to happen" in verdict

    def test_racks_available_ignores_the_fenced(self):
        built = cluster()
        built.heartbeat("b1", now=25)
        built.heartbeat("b3", now=25)
        built.fence_lapsed(now=40)
        assert built.racks_available() == {"rack-a"}
