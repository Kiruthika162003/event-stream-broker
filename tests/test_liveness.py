from __future__ import annotations

import pytest

from relay.errors import Fenced, Invalid
from relay.liveness import LivenessTracker


def tracker() -> LivenessTracker:
    built = LivenessTracker(session_timeout=30)
    built.join("c1", now=0)
    built.join("c2", now=0)
    return built


class TestMembership:
    def test_joining_bumps_the_generation(self):
        built = LivenessTracker(session_timeout=30)
        assert "generation 1" in built.join("c1", now=0)
        assert "generation 2" in built.join("c2", now=0)

    def test_a_bad_timeout_is_refused(self):
        with pytest.raises(Invalid):
            LivenessTracker(session_timeout=0)


class TestHeartbeats:
    def test_a_renewal_keeps_a_member_live(self):
        built = tracker()
        built.heartbeat("c1", now=20)
        built.heartbeat("c2", now=20)
        assert built.sweep(now=40) == []
        assert "c1" in built.live_members()

    def test_a_stranger_cannot_heartbeat(self):
        with pytest.raises(Invalid):
            tracker().heartbeat("ghost", now=5)


class TestEviction:
    def test_silence_past_the_timeout_evicts(self):
        built = tracker()
        built.heartbeat("c1", now=25)
        dead = built.sweep(now=40)
        assert dead == ["c2"]
        assert built.live_members() == ["c1"]

    def test_the_evicted_member_is_fenced_not_welcomed(self):
        built = tracker()
        built.sweep(now=100)
        with pytest.raises(Fenced) as caught:
            built.heartbeat("c1", now=101)
        assert "two consumers own one partition" in str(
            caught.value
        )

    def test_an_eviction_bumps_the_generation(self):
        built = tracker()
        before = built.generation
        built.sweep(now=100)
        assert built.generation == before + 1


class TestStatus:
    def test_suspected_members_are_not_yet_evicted(self):
        built = tracker()
        built.heartbeat("c1", now=18)
        status = built.status(now=20)
        assert "2 live" in status
        assert "1 suspected" in status
        assert "rebalances to a standstill" in status
