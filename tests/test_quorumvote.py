from __future__ import annotations

import pytest

from relay.errors import Fenced, Invalid
from relay.quorumvote import Election, LogEnd


class TestLogRecency:
    def test_a_higher_last_term_wins_regardless_of_length(self):
        a = LogEnd(last_term=5, length=10)
        b = LogEnd(last_term=4, length=1000)
        assert a.at_least_as_current_as(b)

    def test_within_a_term_length_decides(self):
        a = LogEnd(last_term=5, length=10)
        b = LogEnd(last_term=5, length=11)
        assert not a.at_least_as_current_as(b)
        assert b.at_least_as_current_as(a)


class TestMajority:
    def test_majority_of_five_is_three(self):
        e = Election(term=1, voters=5)
        assert e.majority() == 3

    def test_a_zero_voter_election_is_refused(self):
        with pytest.raises(Invalid):
            Election(term=1, voters=0)


class TestRequestVote:
    def test_a_current_candidate_collects_votes_and_wins(self):
        e = Election(term=1, voters=3)
        cand = LogEnd(last_term=1, length=100)
        for voter in ("v1", "v2"):
            assert e.request_vote(voter, cand, LogEnd(1, 100))
        assert e.won()

    def test_a_stale_candidate_is_refused_the_vote(self):
        e = Election(term=1, voters=3)
        cand = LogEnd(last_term=1, length=50)
        granted = e.request_vote("v1", cand, LogEnd(1, 100))
        assert not granted
        assert not e.won()

    def test_a_voter_cannot_vote_twice_in_a_term(self):
        e = Election(term=1, voters=3)
        cand = LogEnd(last_term=1, length=100)
        e.request_vote("v1", cand, LogEnd(1, 100))
        with pytest.raises(Fenced) as caught:
            e.request_vote("v1", cand, LogEnd(1, 100))
        assert "already voted" in str(caught.value)


class TestTally:
    def test_a_win_states_the_majority(self):
        e = Election(term=2, voters=3)
        cand = LogEnd(last_term=2, length=10)
        e.request_vote("v1", cand, LogEnd(2, 10))
        e.request_vote("v2", cand, LogEnd(2, 10))
        assert "won term 2: 2/3, majority 2" in e.tally()

    def test_a_near_miss_reports_how_many_short(self):
        e = Election(term=2, voters=5)
        cand = LogEnd(last_term=2, length=10)
        e.request_vote("v1", cand, LogEnd(2, 10))
        e.request_vote("v2", cand, LogEnd(2, 10))
        assert "short by 1" in e.tally()
