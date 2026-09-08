from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.pagecache import CacheModel


def _model(cached_bytes=1000):
    # 1000 offsets, 10 bytes each = 10000 log bytes.
    return CacheModel(
        log_start=0,
        log_end=1000,
        cached_bytes=cached_bytes,
        bytes_per_offset=10,
    )


class TestCacheEdge:
    def test_the_edge_is_the_log_end_minus_the_cached_span(self):
        # 1000 cached bytes / 10 = 100 offsets cached; edge = 900.
        assert _model().cache_edge() == 900

    def test_a_window_larger_than_the_log_is_refused(self):
        with pytest.raises(Invalid) as caught:
            _model(cached_bytes=100000)
        assert "cannot exceed the log" in str(caught.value)


class TestClassify:
    def test_a_read_near_the_end_is_a_cache_hit(self):
        assert _model().is_cache_hit(950)
        assert "served from cache" in _model().classify(950)

    def test_a_read_far_behind_is_a_disk_fault(self):
        assert not _model().is_cache_hit(100)
        note = _model().classify(100)
        assert "800 offset(s) behind the cache edge" in note
        assert "slows every consumer" in note

    def test_a_read_exactly_at_the_edge_is_a_hit(self):
        assert _model().is_cache_hit(900)
