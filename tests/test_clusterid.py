from __future__ import annotations

import pytest

from relay.clusterid import ClusterIdentity
from relay.errors import Fenced, Invalid


class TestJoin:
    def test_a_matching_id_joins(self):
        c = ClusterIdentity(cluster_id="prod-abc123")
        assert "matches" in c.join("prod-abc123")

    def test_a_mismatched_id_is_fenced(self):
        c = ClusterIdentity(cluster_id="prod-abc123")
        with pytest.raises(Fenced) as caught:
            c.join("staging-xyz789")
        assert "different cluster" in str(caught.value)

    def test_a_fresh_broker_adopts_the_id(self):
        c = ClusterIdentity(cluster_id="prod-abc123")
        assert "adopts cluster id 'prod-abc123'" in c.join(None)

    def test_an_empty_presented_id_is_treated_as_fresh(self):
        c = ClusterIdentity(cluster_id="prod-abc123")
        assert "fresh broker adopts" in c.join("")


class TestImmutability:
    def test_an_empty_cluster_id_is_refused(self):
        with pytest.raises(Invalid):
            ClusterIdentity(cluster_id="")

    def test_renaming_is_refused(self):
        c = ClusterIdentity(cluster_id="prod-abc123")
        with pytest.raises(Invalid) as caught:
            c.rename("prod-new")
        assert "never changes" in str(caught.value)
