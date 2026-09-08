from __future__ import annotations

import pytest

from relay.autocommit import AutoCommitPolicy
from relay.errors import Invalid


class TestReplayWindow:
    def test_the_window_is_interval_times_rate(self):
        policy = AutoCommitPolicy(interval_ticks=50, record_rate=10.0)
        assert policy.replay_window_records() == 500

    def test_the_describe_states_the_window(self):
        policy = AutoCommitPolicy(interval_ticks=50, record_rate=10.0)
        desc = policy.describe()
        assert "replays up to 500 record(s)" in desc
        assert "weighed against the cost of reprocessing" in desc

    def test_a_bad_policy_is_refused(self):
        with pytest.raises(Invalid):
            AutoCommitPolicy(interval_ticks=0, record_rate=1.0)


class TestGuaranteeNote:
    def test_commit_on_poll_warns_about_accidental_loss(self):
        policy = AutoCommitPolicy(interval_ticks=50, record_rate=10.0)
        note = policy.guarantee_note(commits_on_poll=True)
        assert "at-most-once by accident" in note
        assert "commits manually after processing" in note

    def test_commit_after_process_keeps_at_least_once(self):
        policy = AutoCommitPolicy(interval_ticks=50, record_rate=10.0)
        note = policy.guarantee_note(commits_on_poll=False)
        assert "reprocessing, not loss" in note
