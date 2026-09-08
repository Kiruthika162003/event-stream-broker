from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.fetchcoalesce import amplification, coalesce


class TestCoalesce:
    def test_disjoint_ranges_stay_separate(self):
        assert coalesce([(0, 10), (20, 30)]) == [(0, 10), (20, 30)]

    def test_overlapping_ranges_merge(self):
        assert coalesce([(0, 15), (10, 30)]) == [(0, 30)]

    def test_abutting_ranges_merge(self):
        assert coalesce([(0, 10), (10, 20)]) == [(0, 20)]

    def test_unsorted_input_is_sorted_first(self):
        assert coalesce([(20, 30), (0, 25)]) == [(0, 30)]

    def test_a_contained_range_is_absorbed(self):
        assert coalesce([(0, 100), (10, 20)]) == [(0, 100)]

    def test_an_empty_or_backwards_range_is_refused(self):
        with pytest.raises(Invalid) as caught:
            coalesce([(0, 10), (30, 30)])
        assert "empty or backwards" in str(caught.value)

    def test_no_ranges_coalesce_to_nothing(self):
        assert coalesce([]) == []


class TestAmplification:
    def test_it_reports_the_duplicate_reading_avoided(self):
        note = amplification([(0, 20), (10, 30)])
        # raw = 20 + 20 = 40; coalesced = (0,30) = 30; saved = 10
        assert "reading 40 byte(s) raw" in note
        assert "10 byte(s) of duplicate reading avoided" in note
