from __future__ import annotations

import pytest

from relay.errors import Missing
from relay.quotaentity import CLIENT, DEFAULT, PAIR, USER, QuotaResolver


def _resolver():
    return QuotaResolver(
        pair={("alice", "app1"): 100},
        per_user={"alice": 200},
        per_client={"app1": 300},
        cluster_default=500,
    )


class TestPrecedence:
    def test_the_pair_wins_over_all(self):
        limit, level = _resolver().resolve("alice", "app1")
        assert limit == 100
        assert level == PAIR

    def test_user_wins_when_no_pair(self):
        limit, level = _resolver().resolve("alice", "other")
        assert limit == 200
        assert level == USER

    def test_client_wins_when_no_user(self):
        limit, level = _resolver().resolve("bob", "app1")
        assert limit == 300
        assert level == CLIENT

    def test_the_default_fills_the_rest(self):
        limit, level = _resolver().resolve("bob", "other")
        assert limit == 500
        assert level == DEFAULT


class TestNoQuota:
    def test_no_quota_anywhere_is_missing(self):
        r = QuotaResolver()
        with pytest.raises(Missing) as caught:
            r.resolve("x", "y")
        assert "quotas were never configured" in str(caught.value)


class TestDescribe:
    def test_describe_names_the_entity(self):
        note = _resolver().describe("alice", "app1")
        assert "limited to 100 by the user+client entity" in note
