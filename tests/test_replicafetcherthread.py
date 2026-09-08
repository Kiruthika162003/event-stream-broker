from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.replicafetcherthread import ReplicaFetcher


class TestFetch:
    def test_a_fetch_advances_the_offset(self):
        f = ReplicaFetcher(leader_log_end=100)
        received = f.fetch(30)
        assert received == 30
        assert f.fetch_offset == 30

    def test_a_fetch_is_capped_at_what_is_available(self):
        f = ReplicaFetcher(leader_log_end=100, fetch_offset=90)
        received = f.fetch(50)  # only 10 available
        assert received == 10
        assert f.fetch_offset == 100

    def test_a_caught_up_follower_fetches_nothing(self):
        f = ReplicaFetcher(leader_log_end=100, fetch_offset=100)
        assert f.fetch(10) == 0

    def test_repeated_fetches_walk_the_log(self):
        f = ReplicaFetcher(leader_log_end=100)
        f.fetch(40)
        f.fetch(40)
        f.fetch(40)  # capped to reach 100
        assert f.fetch_offset == 100


class TestAckAndLag:
    def test_the_fetch_offset_is_the_acknowledgment(self):
        f = ReplicaFetcher(leader_log_end=100)
        f.fetch(60)
        assert f.acknowledged_through() == 60

    def test_lag_is_the_leader_end_minus_the_fetch_offset(self):
        f = ReplicaFetcher(leader_log_end=100, fetch_offset=70)
        assert f.lag() == 30

    def test_a_caught_up_follower_has_zero_lag(self):
        f = ReplicaFetcher(leader_log_end=100, fetch_offset=100)
        assert f.lag() == 0


class TestRefusals:
    def test_a_fetch_past_the_leader_end_is_refused(self):
        f = ReplicaFetcher(leader_log_end=100, fetch_offset=120)
        with pytest.raises(Invalid) as caught:
            f.fetch(10)
        assert "nothing there to send" in str(caught.value)

    def test_a_negative_count_is_refused(self):
        f = ReplicaFetcher(leader_log_end=100)
        with pytest.raises(Invalid):
            f.fetch(-5)

    def test_a_negative_offset_is_refused(self):
        with pytest.raises(Invalid):
            ReplicaFetcher(leader_log_end=100, fetch_offset=-1)


class TestNote:
    def test_the_note_states_the_lag(self):
        f = ReplicaFetcher(leader_log_end=100, fetch_offset=70)
        assert "lag 30" in f.note()
