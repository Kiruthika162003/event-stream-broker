from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.globaltable import GlobalTable


def _table(est=1000):
    return GlobalTable(
        estimated_bytes=est,
        instance_memory=100_000,
        instances=4,
    )


class TestDeclare:
    def test_a_small_table_is_allowed_global(self):
        t = _table()
        assert not t.loaded

    def test_a_table_too_large_to_fit_is_refused(self):
        with pytest.raises(Invalid) as caught:
            GlobalTable(
                estimated_bytes=50_000,
                instance_memory=100_000,
                instances=4,
            )
        assert "on every instance at once" in str(caught.value)


class TestLookup:
    def test_a_loaded_table_looks_up_any_key(self):
        t = _table()
        t.finish_load({"US": "United States", "IN": "India"})
        assert t.lookup("IN") == "India"

    def test_a_lookup_before_load_is_refused(self):
        t = _table()
        with pytest.raises(Invalid) as caught:
            t.lookup("US")
        assert "still loading" in str(caught.value)

    def test_a_missing_key_is_refused(self):
        t = _table()
        t.finish_load({"US": "United States"})
        with pytest.raises(Invalid):
            t.lookup("ZZ")


class TestFootprint:
    def test_the_footprint_multiplies_across_instances(self):
        t = _table(est=1000)
        note = t.cluster_footprint()
        assert "1000 byte(s) on each of 4 instance(s) = 4000" in note
