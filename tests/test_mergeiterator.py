from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.mergeiterator import merge, merge_report


class TestMerge:
    def test_two_sorted_streams_merge_in_order(self):
        assert merge([[1, 4, 7], [2, 3, 8]]) == [1, 2, 3, 4, 7, 8]

    def test_many_streams_merge(self):
        assert merge([[1, 10], [2, 9], [3, 8]]) == [1, 2, 3, 8, 9, 10]

    def test_an_empty_stream_is_skipped(self):
        assert merge([[], [1, 2], []]) == [1, 2]

    def test_all_empty_merges_to_nothing(self):
        assert merge([[], []]) == []

    def test_an_unsorted_input_is_refused(self):
        with pytest.raises(Invalid) as caught:
            merge([[3, 1, 2]])
        assert "not sorted" in str(caught.value)


class TestDedupe:
    def test_dedupe_collapses_ties(self):
        assert merge([[1, 2, 3], [2, 3, 4]], dedupe=True) == [1, 2, 3, 4]

    def test_without_dedupe_ties_are_kept(self):
        assert merge([[2], [2]]) == [2, 2]


class TestReport:
    def test_report_counts_collapsed(self):
        note = merge_report([[1, 2, 3], [2, 3, 4]], dedupe=True)
        assert "merged 6 element(s) from 2 stream(s) into 4" in note
        assert "2 collapsed by dedupe" in note
