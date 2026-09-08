from __future__ import annotations

import pytest

from relay.aborttransaction import AbortedTransactions
from relay.errors import Invalid


class TestFilter:
    def test_read_committed_drops_aborted_records(self):
        a = AbortedTransactions()
        a.record_abort("p1", first_offset=10)
        records = [(9, "p1"), (10, "p1"), (11, "p1")]
        kept = a.filter_for_read_committed(records)
        # offset 9 is before the abort start, so it survives
        assert kept == [(9, "p1")]

    def test_a_different_producer_is_not_filtered(self):
        a = AbortedTransactions()
        a.record_abort("p1", first_offset=10)
        records = [(10, "p1"), (10, "p2"), (11, "p2")]
        kept = a.filter_for_read_committed(records)
        # p2's records at the same offset range survive
        assert kept == [(10, "p2"), (11, "p2")]

    def test_read_uncommitted_keeps_everything(self):
        a = AbortedTransactions()
        a.record_abort("p1", first_offset=10)
        records = [(10, "p1"), (11, "p1")]
        assert a.filter_for_read_uncommitted(records) == records

    def test_records_before_the_abort_survive(self):
        a = AbortedTransactions()
        a.record_abort("p1", first_offset=50)
        records = [(20, "p1"), (49, "p1"), (50, "p1")]
        kept = a.filter_for_read_committed(records)
        assert kept == [(20, "p1"), (49, "p1")]

    def test_no_aborts_keeps_everything(self):
        a = AbortedTransactions()
        records = [(1, "p1"), (2, "p2")]
        assert a.filter_for_read_committed(records) == records


class TestRefusal:
    def test_a_negative_abort_offset_is_refused(self):
        a = AbortedTransactions()
        with pytest.raises(Invalid):
            a.record_abort("p1", first_offset=-1)


class TestReport:
    def test_the_dropped_count_is_the_number_filtered(self):
        a = AbortedTransactions()
        a.record_abort("p1", first_offset=10)
        records = [(10, "p1"), (11, "p1"), (12, "p2")]
        assert a.dropped_count(records) == 2

    def test_the_note_states_the_dropped_fraction(self):
        a = AbortedTransactions()
        a.record_abort("p1", first_offset=0)
        records = [(0, "p1"), (1, "p2")]
        assert "1/2 record(s) dropped" in a.note(records)
