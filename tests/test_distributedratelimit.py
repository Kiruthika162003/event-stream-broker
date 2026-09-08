from __future__ import annotations

import pytest

from relay.distributedratelimit import DistributedRateLimit
from relay.errors import Invalid


class TestStaticShare:
    def test_the_share_is_the_limit_over_nodes(self):
        d = DistributedRateLimit(global_limit=1000, nodes=4)
        assert d.static_share() == 250


class TestEffective:
    def test_balanced_load_uses_the_full_limit(self):
        d = DistributedRateLimit(global_limit=1000, nodes=4)
        # each node at its 250 share
        assert d.static_effective([250, 250, 250, 250]) == 1000

    def test_skewed_load_wastes_idle_shares(self):
        d = DistributedRateLimit(global_limit=1000, nodes=4)
        # all load on one node: it is capped at 250, the rest idle
        assert d.static_effective([1000, 0, 0, 0]) == 250

    def test_waste_is_the_unused_capacity(self):
        d = DistributedRateLimit(global_limit=1000, nodes=4)
        # demand exceeds the limit but static split serves only 250
        assert d.wasted([1000, 0, 0, 0]) == 750

    def test_no_waste_when_demand_is_under_the_limit(self):
        d = DistributedRateLimit(global_limit=1000, nodes=4)
        assert d.wasted([100, 100, 0, 0]) == 0


class TestConfig:
    def test_zero_nodes_is_refused(self):
        with pytest.raises(Invalid):
            DistributedRateLimit(global_limit=1000, nodes=0)

    def test_a_negative_limit_is_refused(self):
        with pytest.raises(Invalid):
            DistributedRateLimit(global_limit=-1, nodes=4)


class TestReport:
    def test_report_names_the_waste(self):
        d = DistributedRateLimit(global_limit=1000, nodes=4)
        note = d.report([1000, 0, 0, 0])
        assert "750 wasted" in note
        assert "pooling would recover" in note
