from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.fenwicktree import FenwickTree


class TestPrefixSum:
    def test_prefix_sum_accumulates_updates(self):
        t = FenwickTree(size=8)
        t.update(1, 5)
        t.update(3, 7)
        t.update(5, 2)
        assert t.prefix_sum(5) == 14
        assert t.prefix_sum(2) == 5

    def test_it_matches_a_brute_force_prefix_sum(self):
        values = [3, 1, 4, 1, 5, 9, 2, 6]
        t = FenwickTree(size=len(values))
        for i, v in enumerate(values, start=1):
            t.update(i, v)
        for k in range(len(values) + 1):
            assert t.prefix_sum(k) == sum(values[:k])

    def test_a_prefix_sum_of_zero_is_empty(self):
        t = FenwickTree(size=4)
        t.update(1, 9)
        assert t.prefix_sum(0) == 0


class TestRange:
    def test_range_sum_is_a_difference_of_prefixes(self):
        t = FenwickTree(size=8)
        for i in range(1, 9):
            t.update(i, i)
        assert t.range_sum(3, 5) == 3 + 4 + 5

    def test_an_inverted_range_is_refused(self):
        t = FenwickTree(size=8)
        with pytest.raises(Invalid):
            t.range_sum(5, 3)


class TestBounds:
    def test_an_update_out_of_range_is_refused(self):
        t = FenwickTree(size=4)
        with pytest.raises(Invalid):
            t.update(5, 1)

    def test_a_zero_size_is_refused(self):
        with pytest.raises(Invalid):
            FenwickTree(size=0)


class TestTotal:
    def test_total_is_the_full_prefix_sum(self):
        t = FenwickTree(size=4)
        t.update(2, 10)
        t.update(4, 5)
        assert "grand total 15" in t.total()
