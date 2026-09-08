from __future__ import annotations

import pytest

from relay.errors import Fenced, Invalid
from relay.leaderepochfence import LeaderEpochFence


class TestCheck:
    def test_a_matching_epoch_is_served(self):
        f = LeaderEpochFence(broker_epoch=7)
        assert "served by the current leader" in f.check(7)

    def test_an_older_request_epoch_fences_the_client(self):
        f = LeaderEpochFence(broker_epoch=7)
        with pytest.raises(Fenced) as caught:
            f.check(5)
        assert "client's metadata is stale" in str(caught.value)

    def test_a_newer_request_epoch_steps_the_broker_back(self):
        f = LeaderEpochFence(broker_epoch=7)
        with pytest.raises(Fenced) as caught:
            f.check(9)
        assert "this broker is stale" in str(caught.value)

    def test_a_negative_request_epoch_is_refused(self):
        f = LeaderEpochFence(broker_epoch=7)
        with pytest.raises(Invalid):
            f.check(-1)


class TestConfig:
    def test_a_negative_broker_epoch_is_refused(self):
        with pytest.raises(Invalid):
            LeaderEpochFence(broker_epoch=-1)


class TestDirection:
    def test_a_match_agrees(self):
        assert "both sides agree" in LeaderEpochFence(7).mismatch_direction(7)

    def test_broker_behind_is_a_propagation_problem(self):
        note = LeaderEpochFence(7).mismatch_direction(9)
        assert "broker behind" in note
        assert "propagation problem" in note

    def test_client_behind_is_a_stale_cache(self):
        assert "client behind" in LeaderEpochFence(7).mismatch_direction(5)
