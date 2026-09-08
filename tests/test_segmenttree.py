from __future__ import annotations

import random

import pytest

from relay.errors import Invalid
from relay.segmenttree import SegmentTree


class TestRangeMax:
    def test_a_single_range_returns_the_element(self):
        t = SegmentTree(size=5)
        t.update(2, 7.0)
        assert t.range_max(2, 2) == 7.0

    def test_a_range_returns_the_max_within_it(self):
        t = SegmentTree(size=6)
        for i, v in enumerate([3, 1, 4, 1, 5, 9]):
            t.update(i, float(v))
        assert t.range_max(0, 3) == 4.0
        assert t.range_max(2, 5) == 9.0

    def test_the_overall_max_is_the_root(self):
        t = SegmentTree(size=4)
        for i, v in enumerate([2, 8, 1, 6]):
            t.update(i, float(v))
        assert t.overall_max() == 8.0


class TestDecrease:
    def test_lowering_the_current_max_is_handled(self):
        # the case a running scalar cannot do: drop the max, find the next
        t = SegmentTree(size=4)
        for i, v in enumerate([2, 8, 1, 6]):
            t.update(i, float(v))
        t.update(1, 0.0)  # the max drops away
        assert t.overall_max() == 6.0


class TestAgainstBruteForce:
    def test_it_matches_a_brute_force_max_under_random_updates(self):
        rng = random.Random(1234)
        n = 20
        flat = [0.0] * n
        t = SegmentTree(size=n)
        for _ in range(300):
            i = rng.randrange(n)
            v = rng.uniform(-50, 50)
            flat[i] = v
            t.update(i, v)
            lo = rng.randrange(n)
            hi = rng.randrange(lo, n)
            assert t.range_max(lo, hi) == max(flat[lo : hi + 1])


class TestRefusals:
    def test_an_out_of_range_update_is_refused(self):
        t = SegmentTree(size=3)
        with pytest.raises(Invalid):
            t.update(5, 1.0)

    def test_an_inverted_range_is_refused(self):
        t = SegmentTree(size=5)
        with pytest.raises(Invalid) as caught:
            t.range_max(4, 1)
        assert "inverted" in str(caught.value)

    def test_a_range_outside_the_array_is_refused(self):
        t = SegmentTree(size=5)
        with pytest.raises(Invalid):
            t.range_max(0, 9)

    def test_a_zero_size_tree_is_refused(self):
        with pytest.raises(Invalid):
            SegmentTree(size=0)


class TestNote:
    def test_the_note_states_the_root(self):
        t = SegmentTree(size=2)
        t.update(0, 3.0)
        t.update(1, 9.0)
        assert "root max 9.0" in t.note()
