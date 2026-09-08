from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.hintedhandoff import HintedHandoff


class TestStore:
    def test_a_hint_is_stored_for_a_down_replica(self):
        h = HintedHandoff(hint_window=100)
        assert "hint stored" in h.store_hint("r1", now=0, write="w1", replica_up=False)

    def test_a_hint_for_an_up_replica_is_refused(self):
        h = HintedHandoff(hint_window=100)
        with pytest.raises(Invalid) as caught:
            h.store_hint("r1", now=0, write="w1", replica_up=True)
        assert "take the write directly" in str(caught.value)


class TestReplay:
    def test_replay_returns_hints_in_order(self):
        h = HintedHandoff(hint_window=100)
        h.store_hint("r1", 0, "w1", replica_up=False)
        h.store_hint("r1", 1, "w2", replica_up=False)
        assert h.replay("r1", now=2) == ["w1", "w2"]

    def test_replay_clears_the_hints(self):
        h = HintedHandoff(hint_window=100)
        h.store_hint("r1", 0, "w1", replica_up=False)
        h.replay("r1", now=1)
        assert h.replay("r1", now=2) == []

    def test_expired_hints_are_not_replayed(self):
        h = HintedHandoff(hint_window=100)
        h.store_hint("r1", 0, "old", replica_up=False)
        h.store_hint("r1", 150, "new", replica_up=False)
        # at now=200, the hint from t=0 is past the 100 window
        assert h.replay("r1", now=200) == ["new"]


class TestPending:
    def test_pending_counts_live_hints(self):
        h = HintedHandoff(hint_window=100)
        h.store_hint("r1", 0, "w1", replica_up=False)
        h.store_hint("r1", 5, "w2", replica_up=False)
        assert "2 hint(s) pending" in h.pending("r1", now=10)


class TestConfig:
    def test_a_zero_window_is_refused(self):
        with pytest.raises(Invalid):
            HintedHandoff(hint_window=0)
