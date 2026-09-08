from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.heartbeatthread import LivenessTimers


def timers() -> LivenessTimers:
    t = LivenessTimers(session_timeout=30, max_poll_interval=300)
    t.poll(now=0)
    return t


class TestSeparation:
    def test_a_slow_processor_that_heartbeats_stays_alive(self):
        t = timers()
        # 200 ticks since poll (under max-poll 300), heartbeat kept fresh
        t.heartbeat(now=200)
        assert "healthy" in t.evaluate(now=200)

    def test_a_dead_process_fails_the_session_timeout(self):
        t = timers()
        # no heartbeat since 0, now 40 > session 30
        verdict = t.evaluate(now=40)
        assert "session timeout" in verdict
        assert "not a stuck processor" in verdict

    def test_a_wedged_processor_fails_max_poll(self):
        t = timers()
        # heartbeat fresh but no poll since 0, now 400 > 300
        for beat in range(0, 400, 20):
            t.heartbeat(now=beat)
        verdict = t.evaluate(now=400)
        assert "max-poll-interval" in verdict
        assert "not a network problem" in verdict


class TestRefusals:
    def test_bad_timers_are_refused(self):
        with pytest.raises(Invalid):
            LivenessTimers(session_timeout=0, max_poll_interval=1)

    def test_poll_refreshes_both_clocks(self):
        t = timers()
        t.poll(now=100)
        assert t.last_heartbeat == 100
        assert t.last_poll == 100
