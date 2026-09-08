from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.offsetfetch import NO_OFFSET, OffsetFetchResponse


class TestFetch:
    def test_a_committed_partition_returns_its_offset(self):
        r = OffsetFetchResponse(log_ends={"t-0": 1000})
        r.commit("t-0", 400)
        assert r.fetch("t-0") == 400

    def test_a_never_committed_partition_returns_the_sentinel(self):
        r = OffsetFetchResponse(log_ends={"t-0": 1000})
        assert r.fetch("t-0") == NO_OFFSET

    def test_a_commit_past_the_log_end_is_refused(self):
        r = OffsetFetchResponse(log_ends={"t-0": 1000})
        with pytest.raises(Invalid) as caught:
            r.commit("t-0", 2000)
        assert "past its log end" in str(caught.value)


class TestResumeOrReset:
    def test_zero_is_a_real_commit_not_no_commit(self):
        r = OffsetFetchResponse(log_ends={"t-0": 1000})
        r.commit("t-0", 0)
        assert "resume at committed offset 0" in r.resume_or_reset("t-0")

    def test_no_commit_falls_back_to_the_reset_policy(self):
        r = OffsetFetchResponse(log_ends={"t-0": 1000})
        note = r.resume_or_reset("t-0")
        assert "fall back to the reset policy" in note
        assert "not offset zero" in note


class TestSummary:
    def test_it_counts_resume_against_reset(self):
        r = OffsetFetchResponse(log_ends={"t-0": 1000, "t-1": 1000, "t-2": 1000})
        r.commit("t-0", 100)
        r.commit("t-1", 200)
        note = r.summary(["t-0", "t-1", "t-2"])
        assert "2 partition(s) resume from a commit, 1 reset" in note
