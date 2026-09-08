from __future__ import annotations

from relay.abortedindex import AbortedIndex, AbortedTxn


class TestIsAborted:
    def test_a_covered_offset_of_the_right_producer_is_aborted(self):
        idx = AbortedIndex()
        idx.record(AbortedTxn(producer_id=7, first_offset=10, last_offset=20))
        assert idx.is_aborted(7, 15)

    def test_the_same_offset_of_another_producer_is_not(self):
        idx = AbortedIndex()
        idx.record(AbortedTxn(producer_id=7, first_offset=10, last_offset=20))
        assert not idx.is_aborted(8, 15)

    def test_an_offset_outside_the_range_is_not_aborted(self):
        idx = AbortedIndex()
        idx.record(AbortedTxn(producer_id=7, first_offset=10, last_offset=20))
        assert not idx.is_aborted(7, 25)


class TestPrune:
    def test_entries_entirely_below_the_log_start_are_dropped(self):
        idx = AbortedIndex()
        idx.record(AbortedTxn(producer_id=1, first_offset=0, last_offset=5))
        idx.record(AbortedTxn(producer_id=1, first_offset=100, last_offset=110))
        dropped = idx.prune_below(50)
        assert dropped == 1
        assert len(idx.entries) == 1

    def test_an_entry_straddling_the_start_is_kept(self):
        idx = AbortedIndex()
        idx.record(AbortedTxn(producer_id=1, first_offset=40, last_offset=60))
        assert idx.prune_below(50) == 0


class TestFilterRatio:
    def test_the_ratio_counts_aborted_fetched_records(self):
        idx = AbortedIndex()
        idx.record(AbortedTxn(producer_id=1, first_offset=0, last_offset=10))
        fetched = [(1, 2), (1, 5), (2, 5), (1, 50)]
        note = idx.filter_ratio(fetched)
        assert "2/4 fetched record(s) aborted (50%)" in note
        assert "throughput spent" in note

    def test_an_empty_fetch_has_nothing_to_skip(self):
        idx = AbortedIndex()
        assert "nothing fetched" in idx.filter_ratio([])
