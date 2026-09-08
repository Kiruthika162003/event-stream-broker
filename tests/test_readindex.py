from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.readindex import ReadIndex


class TestServe:
    def test_a_confirmed_caught_up_leader_serves(self):
        r = ReadIndex(commit_index=100, voters=3)
        r.begin_read()
        r.confirm()  # 2/3 with the leader's own vote
        r.apply_to(100)
        assert "served as of index 100" in r.serve()

    def test_serving_without_quorum_is_refused(self):
        r = ReadIndex(commit_index=100, voters=5)
        r.begin_read()  # only the leader itself
        r.apply_to(100)
        with pytest.raises(Invalid) as caught:
            r.serve()
        assert "must step down" in str(caught.value)

    def test_serving_before_the_apply_catches_up_is_refused(self):
        r = ReadIndex(commit_index=100, voters=3)
        r.begin_read()
        r.confirm()
        r.apply_to(50)  # behind the read index
        with pytest.raises(Invalid) as caught:
            r.serve()
        assert "wait for it to catch up" in str(caught.value)

    def test_serving_before_begin_is_refused(self):
        r = ReadIndex(commit_index=100, voters=3)
        with pytest.raises(Invalid):
            r.serve()


class TestQuorum:
    def test_majority_of_five_is_three(self):
        r = ReadIndex(commit_index=0, voters=5)
        r.begin_read()
        r.confirm()
        assert not r.quorum_confirmed()
        r.confirm()
        assert r.quorum_confirmed()


class TestConfig:
    def test_zero_voters_is_refused(self):
        with pytest.raises(Invalid):
            ReadIndex(commit_index=0, voters=0)
