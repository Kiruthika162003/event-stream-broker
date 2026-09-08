from __future__ import annotations

import pytest

from relay.apirouter import ApiRouter
from relay.errors import Invalid, Missing


def _router():
    r = ApiRouter()
    r.register("produce", min_version=3, max_version=9)
    r.register("fetch", min_version=4, max_version=13)
    return r


class TestRoute:
    def test_a_supported_key_and_version_routes(self):
        assert "routed 'produce' v7" in _router().route("produce", 7)

    def test_an_unknown_key_is_missing(self):
        with pytest.raises(Missing) as caught:
            _router().route("smoke", 1)
        assert "does not" in str(caught.value)
        assert "implement it" in str(caught.value)

    def test_a_version_below_the_minimum_is_refused(self):
        with pytest.raises(Invalid) as caught:
            _router().route("produce", 1)
        assert "negotiate up to the supported range 3..9" in str(caught.value)

    def test_a_version_above_the_maximum_is_refused(self):
        with pytest.raises(Invalid) as caught:
            _router().route("produce", 20)
        assert "negotiate down to the supported range 3..9" in str(caught.value)


class TestRegister:
    def test_an_inverted_range_is_refused(self):
        r = ApiRouter()
        with pytest.raises(Invalid):
            r.register("x", min_version=9, max_version=3)


class TestAdvertised:
    def test_advertised_versions_report_the_ranges(self):
        assert _router().advertised_versions()["fetch"] == (4, 13)
