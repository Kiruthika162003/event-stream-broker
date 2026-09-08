from __future__ import annotations

import random

import pytest

from relay.errors import Invalid
from relay.quickselect import kth_smallest, note, percentile


class TestKthSmallest:
    def test_the_smallest_is_rank_zero(self):
        assert kth_smallest([5, 3, 8, 1, 9], 0) == 1

    def test_the_largest_is_the_last_rank(self):
        assert kth_smallest([5, 3, 8, 1, 9], 4) == 9

    def test_a_middle_rank_is_the_median(self):
        assert kth_smallest([5, 3, 8, 1, 9], 2) == 5

    def test_it_matches_a_full_sort_on_random_input(self):
        rng = random.Random(99)
        for _ in range(200):
            n = rng.randint(1, 40)
            data = [rng.uniform(-100, 100) for _ in range(n)]
            k = rng.randrange(n)
            assert kth_smallest(data, k) == sorted(data)[k]

    def test_it_handles_duplicates(self):
        data = [4, 4, 4, 2, 2, 9]
        assert kth_smallest(data, 0) == 2
        assert kth_smallest(data, 5) == 9

    def test_it_handles_already_sorted_input(self):
        # the worst case for a naive first-element pivot
        data = list(range(100))
        assert kth_smallest([float(x) for x in data], 50) == 50


class TestPercentile:
    def test_p99_of_a_hundred_is_near_the_top(self):
        data = [float(i) for i in range(100)]  # 0..99
        assert percentile(data, 99) == 99

    def test_the_median_is_the_fiftieth_percentile(self):
        data = [float(i) for i in range(101)]  # 0..100
        assert percentile(data, 50) == 50

    def test_the_zeroth_percentile_is_the_minimum(self):
        assert percentile([3.0, 1.0, 2.0], 0) == 1.0


class TestRefusals:
    def test_an_empty_batch_has_no_kth(self):
        with pytest.raises(Invalid):
            kth_smallest([], 0)

    def test_a_rank_out_of_range_is_refused(self):
        with pytest.raises(Invalid):
            kth_smallest([1, 2, 3], 5)

    def test_a_percentile_outside_the_range_is_refused(self):
        with pytest.raises(Invalid):
            percentile([1.0, 2.0], 150)

    def test_an_empty_percentile_is_refused(self):
        with pytest.raises(Invalid):
            percentile([], 50)


class TestNote:
    def test_the_note_counts_the_batch(self):
        assert "3 value(s)" in note([1.0, 2.0, 3.0])
