from __future__ import annotations

import pytest

from relay.countminsketch import CountMinSketch
from relay.errors import Invalid


class TestCount:
    def test_it_counts_a_key(self):
        s = CountMinSketch(rows=4, cols=1000)
        for _ in range(10):
            s.add("hot")
        assert s.estimate("hot") >= 10

    def test_it_never_underestimates(self):
        s = CountMinSketch(rows=5, cols=2000)
        truth = {}
        for i in range(500):
            key = f"k{i % 50}"
            s.add(key)
            truth[key] = truth.get(key, 0) + 1
        # the defining guarantee: estimate is always >= true count
        for key, count in truth.items():
            assert s.estimate(key) >= count

    def test_an_unseen_key_estimates_low(self):
        s = CountMinSketch(rows=4, cols=1000)
        s.add("seen", 5)
        assert s.estimate("never-added") <= 5


class TestHeavyHitter:
    def test_a_frequent_key_is_a_heavy_hitter(self):
        s = CountMinSketch(rows=4, cols=1000)
        for _ in range(100):
            s.add("hot")
        assert s.is_heavy_hitter("hot", threshold=50)

    def test_a_rare_key_is_not(self):
        s = CountMinSketch(rows=4, cols=1000)
        s.add("cold")
        assert not s.is_heavy_hitter("cold", threshold=50)


class TestConfig:
    def test_zero_rows_is_refused(self):
        with pytest.raises(Invalid):
            CountMinSketch(rows=0, cols=10)

    def test_a_non_positive_count_is_refused(self):
        s = CountMinSketch(rows=4, cols=10)
        with pytest.raises(Invalid):
            s.add("k", 0)
