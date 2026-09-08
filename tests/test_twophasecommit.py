from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.twophasecommit import ABORT, COMMIT, TwoPhaseCommit


def _txn():
    return TwoPhaseCommit(participants={"p1", "p2", "p3"})


class TestVote:
    def test_unanimous_yes_commits(self):
        t = _txn()
        for p in ("p1", "p2", "p3"):
            t.vote(p, "yes")
        assert "commit" in t.decide()
        assert t.decision == COMMIT

    def test_any_no_aborts(self):
        t = _txn()
        t.vote("p1", "yes")
        t.vote("p2", "no")
        t.vote("p3", "yes")
        t.decide()
        assert t.decision == ABORT

    def test_a_changed_vote_is_refused(self):
        t = _txn()
        t.vote("p1", "yes")
        with pytest.raises(Invalid) as caught:
            t.vote("p1", "no")
        assert "cannot be changed" in str(caught.value)

    def test_deciding_before_all_voted_is_refused(self):
        t = _txn()
        t.vote("p1", "yes")
        with pytest.raises(Invalid) as caught:
            t.decide()
        assert "waits for all" in str(caught.value)


class TestBlocking:
    def test_a_yes_voter_without_the_verdict_is_blocked(self):
        t = _txn()
        for p in ("p1", "p2", "p3"):
            t.vote(p, "yes")
        # coordinator crashed before sending the decision
        note = t.participant_state("p1", heard_decision=False)
        assert "BLOCKED" in note

    def test_a_yes_voter_with_the_verdict_applies_it(self):
        t = _txn()
        for p in ("p1", "p2", "p3"):
            t.vote(p, "yes")
        t.decide()
        assert "applies the commit" in t.participant_state("p1", heard_decision=True)


class TestConfig:
    def test_no_participants_is_refused(self):
        with pytest.raises(Invalid):
            TwoPhaseCommit(participants=set())
