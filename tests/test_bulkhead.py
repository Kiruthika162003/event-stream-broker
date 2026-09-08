from __future__ import annotations

import pytest

from relay.bulkhead import Bulkhead
from relay.errors import Invalid


def _bulkhead():
    return Bulkhead(pool_sizes={"produce": 2, "fetch": 2, "heartbeat": 1})


class TestAcquire:
    def test_it_acquires_within_a_pool(self):
        b = _bulkhead()
        assert "acquired a 'produce' thread, 1/2" in b.acquire("produce")

    def test_a_full_pool_rejects_but_contains(self):
        b = _bulkhead()
        b.acquire("fetch")
        b.acquire("fetch")
        with pytest.raises(Invalid) as caught:
            b.acquire("fetch")
        assert "contained to this class" in str(caught.value)

    def test_one_full_pool_does_not_starve_another(self):
        b = _bulkhead()
        b.acquire("fetch")
        b.acquire("fetch")  # fetch full
        # produce still has its own threads
        assert "acquired a 'produce' thread" in b.acquire("produce")

    def test_an_unknown_class_is_refused(self):
        with pytest.raises(Invalid):
            _bulkhead().acquire("gossip")


class TestRelease:
    def test_release_frees_a_thread(self):
        b = _bulkhead()
        b.acquire("fetch")
        b.acquire("fetch")
        b.release("fetch")
        assert "acquired a 'fetch' thread, 2/2" in b.acquire("fetch")


class TestConfig:
    def test_a_zero_pool_is_refused(self):
        with pytest.raises(Invalid):
            Bulkhead(pool_sizes={"x": 0})


class TestUtilization:
    def test_utilization_reports_each_pool(self):
        b = _bulkhead()
        b.acquire("produce")
        note = b.utilization()
        assert "produce 1/2" in note
        assert "fetch 0/2" in note
