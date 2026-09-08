from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.maxpoll import ProgressTracker


def tracker() -> ProgressTracker:
    built = ProgressTracker(
        session_timeout=30, max_poll_interval=100
    )
    built.register("c1", now=0)
    return built


class TestTwoLivenesses:
    def test_max_poll_must_exceed_the_session_timeout(self):
        with pytest.raises(Invalid) as caught:
            ProgressTracker(session_timeout=100, max_poll_interval=30)
        assert "collapse into one" in str(caught.value)

    def test_a_dead_consumer_is_evicted_for_no_heartbeat(self):
        chosen = tracker()
        evicted = chosen.sweep(now=40)
        assert evicted == ["c1"]
        assert "died" in chosen.reason_for("c1")

    def test_a_livelocked_consumer_is_evicted_for_no_poll(self):
        chosen = tracker()
        for tick in range(10, 130, 20):
            chosen.heartbeat("c1", now=tick)
        evicted = chosen.sweep(now=130)
        assert evicted == ["c1"]
        assert "livelocked" in chosen.reason_for("c1")

    def test_a_polling_consumer_stays_healthy(self):
        chosen = tracker()
        for tick in range(20, 200, 20):
            chosen.poll("c1", now=tick)
        assert chosen.sweep(now=200) == []
        assert "healthy" in chosen.reason_for("c1")


class TestRefusals:
    def test_heartbeat_from_an_evicted_consumer_is_refused(self):
        chosen = tracker()
        chosen.sweep(now=40)
        with pytest.raises(Invalid):
            chosen.heartbeat("c1", now=41)

    def test_reason_for_an_unknown_consumer_is_refused(self):
        with pytest.raises(Invalid):
            tracker().reason_for("ghost")
