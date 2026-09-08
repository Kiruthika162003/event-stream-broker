from __future__ import annotations

import pytest

from relay.election import Candidate, PartitionElector
from relay.errors import Fenced, Invalid


def elector() -> PartitionElector:
    return PartitionElector(epoch=4, committed_offset=100)


class TestEligibility:
    def test_the_longest_eligible_log_wins(self):
        result = elector().elect(
            [
                Candidate("f1", log_end_offset=105, in_sync=True),
                Candidate("f2", log_end_offset=110, in_sync=True),
                Candidate("f3", log_end_offset=100, in_sync=True),
            ]
        )
        assert result.leader == "f2"
        assert result.epoch == 5

    def test_a_replica_missing_the_commit_is_ineligible(self):
        result = elector().elect(
            [
                Candidate("behind", log_end_offset=90, in_sync=True),
                Candidate("caught", log_end_offset=100, in_sync=True),
            ]
        )
        assert result.leader == "caught"

    def test_out_of_sync_replicas_are_ineligible(self):
        with pytest.raises(Invalid):
            elector().elect(
                [
                    Candidate("x", log_end_offset=200, in_sync=False),
                ]
            )

    def test_no_candidates_leaves_the_partition_dark(self):
        with pytest.raises(Invalid):
            elector().elect([])


class TestTruncation:
    def test_followers_truncate_to_the_new_leader(self):
        result = elector().elect(
            [
                Candidate("f1", log_end_offset=105, in_sync=True),
                Candidate("f2", log_end_offset=120, in_sync=True),
            ]
        )
        assert result.leader == "f2"
        assert "truncate to 120" in result.truncation_note
        assert "0 record(s) beyond" in result.truncation_note


class TestUncleanElection:
    def test_unclean_is_refused_by_default(self):
        with pytest.raises(Invalid) as caught:
            elector().elect(
                [Candidate("stale", 50, in_sync=False)]
            )
        assert "must be an explicit unclean election" in str(
            caught.value
        )

    def test_unclean_is_allowed_when_named(self):
        result = elector().elect(
            [Candidate("stale", 50, in_sync=False)],
            allow_unclean=True,
        )
        assert result.unclean
        assert result.leader == "stale"


class TestFencing:
    def test_a_prior_epoch_message_is_fenced(self):
        chosen = elector()
        with pytest.raises(Fenced) as caught:
            chosen.accept_from(3)
        assert "split-brain that diverges" in str(caught.value)

    def test_the_current_epoch_is_accepted(self):
        elector().accept_from(4)
