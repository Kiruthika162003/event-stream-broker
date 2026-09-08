from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.rangequery import SortedIndex


def _idx():
    return SortedIndex(keys=[10, 20, 30, 40, 50])


class TestRange:
    def test_it_returns_the_slice_in_range(self):
        assert _idx().range(20, 40) == [20, 30, 40]

    def test_bounds_are_inclusive(self):
        assert _idx().range(10, 10) == [10]

    def test_a_range_between_keys_is_empty(self):
        assert _idx().range(21, 29) == []

    def test_a_range_outside_the_index_is_empty(self):
        assert _idx().range(100, 200) == []

    def test_an_inverted_range_is_refused(self):
        with pytest.raises(Invalid) as caught:
            _idx().range(40, 20)
        assert "inverted range" in str(caught.value)


class TestSorted:
    def test_an_unsorted_index_is_refused(self):
        with pytest.raises(Invalid):
            SortedIndex(keys=[3, 1, 2])


class TestSelectivity:
    def test_a_narrow_range_is_reported(self):
        note = _idx().selectivity(20, 30)
        assert "2/5 entries in range (40%)" in note

    def test_an_empty_index_notes_nothing(self):
        assert "nothing to scan" in SortedIndex().selectivity(0, 10)
