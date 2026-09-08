from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.flexiblequorum import FlexibleQuorum


class TestIntersection:
    def test_a_small_replication_quorum_with_a_large_election_is_safe(self):
        # N=5, Q1=4, Q2=2 -> 6 > 5
        q = FlexibleQuorum(nodes=5, election_quorum=4, replication_quorum=2)
        assert q.intersects()
        assert "safe" in q.validate()

    def test_two_minorities_do_not_intersect(self):
        # N=5, Q1=2, Q2=2 -> 4 <= 5
        q = FlexibleQuorum(nodes=5, election_quorum=2, replication_quorum=2)
        assert not q.intersects()
        with pytest.raises(Invalid) as caught:
            q.validate()
        assert "could miss a committed entry" in str(caught.value)

    def test_two_majorities_still_work(self):
        q = FlexibleQuorum(nodes=5, election_quorum=3, replication_quorum=3)
        assert q.intersects()


class TestTradeoff:
    def test_a_small_replication_quorum_tolerates_more_commit_failures(self):
        q = FlexibleQuorum(nodes=5, election_quorum=4, replication_quorum=2)
        assert q.commit_failures_tolerated() == 3
        assert q.election_failures_tolerated() == 1


class TestConfig:
    def test_a_quorum_above_n_is_refused(self):
        with pytest.raises(Invalid):
            FlexibleQuorum(nodes=3, election_quorum=4, replication_quorum=2)
