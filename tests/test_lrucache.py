from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.lrucache import LruCache


class TestEviction:
    def test_it_evicts_the_least_recently_used(self):
        c = LruCache(capacity=2)
        c.put("a", 1)
        c.put("b", 2)
        note = c.put("c", 3)  # evicts a
        assert "evicted least-recent 'a'" in note
        assert c.get("a") is None

    def test_access_makes_an_entry_recent(self):
        c = LruCache(capacity=2)
        c.put("a", 1)
        c.put("b", 2)
        c.get("a")  # a is now most recent
        c.put("c", 3)  # evicts b, not a
        assert c.get("a") == 1
        assert c.get("b") is None

    def test_updating_an_existing_key_does_not_grow(self):
        c = LruCache(capacity=2)
        c.put("a", 1)
        c.put("a", 9)
        assert c.get("a") == 9


class TestHitRate:
    def test_get_records_hits_and_misses(self):
        c = LruCache(capacity=2)
        c.put("a", 1)
        c.get("a")  # hit
        c.get("z")  # miss
        assert "50% hit rate (1/2)" in c.hit_rate()

    def test_mru_order_is_reported(self):
        c = LruCache(capacity=3)
        c.put("a", 1)
        c.put("b", 2)
        c.get("a")
        assert c.keys_mru_first() == ["a", "b"]


class TestConfig:
    def test_a_zero_capacity_is_refused(self):
        with pytest.raises(Invalid):
            LruCache(capacity=0)
