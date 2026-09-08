from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.interactivequery import QueryRouter


def _router():
    r = QueryRouter(partitions=4)
    r.owners = {0: "i0", 1: "i1", 2: "i2", 3: "i3"}
    return r


class TestRoute:
    def test_a_query_at_the_owner_is_served_locally(self):
        r = _router()
        key = "k"
        owner = r.owner_of(key)
        assert "served" in r.route(key, arrived_at=owner)

    def test_a_query_at_the_wrong_instance_is_redirected(self):
        r = _router()
        key = "k"
        owner = r.owner_of(key)
        other = "i9"
        note = r.route(key, arrived_at=other)
        assert f"to its owner '{owner}'" in note

    def test_a_partition_with_no_owner_is_refused(self):
        r = QueryRouter(partitions=4)  # no owners set
        with pytest.raises(Invalid) as caught:
            r.owner_of("k")
        assert "must retry after a takeover" in str(caught.value)


class TestFallback:
    def test_the_active_serves_when_present(self):
        r = _router()
        # find a key and ensure its active is used
        assert "active owner" in r.route_with_fallback("k")

    def test_a_standby_serves_when_the_active_is_down(self):
        r = QueryRouter(partitions=1)
        r.owners = {}
        r.standbys = {0: "standby0"}
        note = r.route_with_fallback("k")
        assert "served by standby 'standby0'" in note
        assert "stale-read" in note

    def test_no_active_or_standby_is_unavailable(self):
        r = QueryRouter(partitions=1)
        with pytest.raises(Invalid):
            r.route_with_fallback("k")


class TestConfig:
    def test_zero_partitions_is_refused(self):
        with pytest.raises(Invalid):
            QueryRouter(partitions=0)
