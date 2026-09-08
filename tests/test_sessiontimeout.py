from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.sessiontimeout import SessionTiming


class TestBeats:
    def test_beats_per_window_is_the_ratio(self):
        t = SessionTiming(heartbeat_interval=1000, session_timeout=3000)
        assert t.beats_per_window() == 3
        assert t.tolerated_misses() == 2

    def test_an_interval_at_the_timeout_is_refused(self):
        with pytest.raises(Invalid) as caught:
            SessionTiming(heartbeat_interval=3000, session_timeout=3000)
        assert "no margin at all" in str(caught.value)

    def test_a_non_positive_timeout_is_refused(self):
        with pytest.raises(Invalid):
            SessionTiming(heartbeat_interval=1, session_timeout=0)


class TestAssess:
    def test_too_few_beats_risks_false_eviction(self):
        t = SessionTiming(heartbeat_interval=2000, session_timeout=3000)
        assert "evicts a healthy member" in t.assess()

    def test_a_good_ratio_tolerates_misses(self):
        t = SessionTiming(heartbeat_interval=1000, session_timeout=3000)
        assert "a non-event, not a rebalance" in t.assess()

    def test_too_many_beats_is_wasteful(self):
        t = SessionTiming(heartbeat_interval=100, session_timeout=3000)
        assert "wasting network" in t.assess()
