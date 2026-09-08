from __future__ import annotations

import pytest

from relay.commitindex import CommitIndex
from relay.errors import Invalid


def _ci():
    return CommitIndex(
        current_term=5,
        entry_terms={1: 3, 2: 3, 3: 5, 4: 5},
        voters=3,
    )


class TestCurrentTerm:
    def test_a_current_term_entry_on_a_majority_commits(self):
        ci = _ci()
        assert "committed to index 3" in ci.try_advance(3, replica_count=2)
        assert ci.commit_index == 3

    def test_below_majority_is_not_committable(self):
        ci = _ci()
        with pytest.raises(Invalid) as caught:
            ci.try_advance(3, replica_count=1)
        assert "below majority" in str(caught.value)


class TestPriorTerm:
    def test_committing_a_prior_term_entry_directly_is_refused(self):
        ci = _ci()
        with pytest.raises(Invalid) as caught:
            ci.try_advance(2, replica_count=3)  # index 2 is term 3
        assert "figure-8 bug" in str(caught.value)

    def test_a_prior_term_entry_commits_via_a_current_term_one(self):
        ci = _ci()
        note = ci.commit_prior_via_current(prior_index=2, current_index=3)
        assert "safely committed by log matching" in note
        assert ci.commit_index == 3

    def test_the_current_entry_must_be_beyond_the_prior(self):
        ci = _ci()
        with pytest.raises(Invalid):
            ci.commit_prior_via_current(prior_index=4, current_index=3)

    def test_a_non_current_carrier_is_refused(self):
        ci = _ci()
        with pytest.raises(Invalid) as caught:
            ci.commit_prior_via_current(prior_index=1, current_index=2)  # 2 is term 3
        assert "not a current-term entry" in str(caught.value)


class TestUnknown:
    def test_an_unknown_index_is_refused(self):
        with pytest.raises(Invalid):
            _ci().try_advance(99, replica_count=3)
