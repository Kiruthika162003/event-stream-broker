from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.reservoirsample import Reservoir


class TestFill:
    def test_the_first_k_items_fill_the_reservoir(self):
        r = Reservoir(size=3)
        for v in (1, 2, 3):
            r.offer(v)
        assert r.sample() == [1, 2, 3]

    def test_a_short_stream_is_the_whole_sample(self):
        r = Reservoir(size=5)
        r.offer(1)
        r.offer(2)
        assert r.sample() == [1, 2]
        assert "shorter than the sample" in r.fill_note()


class TestReplacement:
    def test_a_roll_that_hits_replaces_the_slot(self):
        r = Reservoir(size=3)
        for v in (1, 2, 3):
            r.offer(v)
        # 4th item; roll returns slot 0 -> replaces reservoir[0]
        r.offer(4, roll=lambda _n: 0)
        assert r.sample() == [4, 2, 3]

    def test_a_roll_that_misses_keeps_the_reservoir(self):
        r = Reservoir(size=3)
        for v in (1, 2, 3):
            r.offer(v)
        # roll returns an index >= size -> no replacement
        r.offer(4, roll=lambda _n: 99)
        assert r.sample() == [1, 2, 3]


class TestConfig:
    def test_a_zero_size_is_refused(self):
        with pytest.raises(Invalid):
            Reservoir(size=0)


class TestSeen:
    def test_seen_counts_every_offer(self):
        r = Reservoir(size=2)
        for v in range(10):
            r.offer(v, roll=lambda _n: 99)
        assert r.seen == 10
        assert "full at 2" in r.fill_note()
