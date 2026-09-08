from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.quorumobserver import QuorumMembership


def _quorum():
    return QuorumMembership(
        leader_offset=1000,
        max_promote_lag=50,
        voters={"v1", "v2", "v3"},
    )


class TestMajority:
    def test_observers_never_change_the_commit_majority(self):
        q = _quorum()
        assert q.commit_majority() == 2
        q.add_observer("o1", offset=990)
        q.add_observer("o2", offset=980)
        assert q.commit_majority() == 2

    def test_an_observer_that_is_already_a_voter_is_refused(self):
        q = _quorum()
        with pytest.raises(Invalid):
            q.add_observer("v1", offset=990)


class TestPromote:
    def test_a_caught_up_observer_is_promoted(self):
        q = _quorum()
        q.add_observer("o1", offset=990)
        note = q.promote("o1")
        assert "commit majority now 3" in note
        assert "o1" in q.voters

    def test_a_lagging_observer_is_refused(self):
        q = _quorum()
        q.add_observer("o1", offset=800)
        with pytest.raises(Invalid) as caught:
            q.promote("o1")
        assert "weakening the majority" in str(caught.value)

    def test_promoting_a_non_observer_is_refused(self):
        q = _quorum()
        with pytest.raises(Invalid):
            q.promote("ghost")


class TestReport:
    def test_it_separates_voters_from_observers(self):
        q = _quorum()
        q.add_observer("o1", offset=990)
        note = q.report()
        assert "3 voter(s) needing 2 to commit" in note
        assert "1 observer(s)" in note
