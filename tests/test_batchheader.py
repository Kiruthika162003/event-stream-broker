from __future__ import annotations

import pytest

from relay.batchheader import BatchHeader
from relay.errors import Invalid


def _header(base=100, last_delta=9, count=10):
    return BatchHeader(
        base_offset=base,
        last_offset_delta=last_delta,
        base_timestamp=1000,
        record_count=count,
    )


class TestOffsets:
    def test_last_offset_is_base_plus_delta(self):
        assert _header().last_offset() == 109

    def test_next_base_is_one_past_the_last(self):
        assert _header().next_base_offset() == 110

    def test_a_record_offset_is_base_plus_its_delta(self):
        assert _header().offset_of(3) == 103

    def test_a_delta_past_the_stated_end_is_refused(self):
        with pytest.raises(Invalid) as caught:
            _header().offset_of(10)
        assert "past the" in str(caught.value)


class TestFollows:
    def test_a_batch_follows_when_its_base_is_the_prior_next(self):
        first = _header(base=100, last_delta=9)
        second = _header(base=110, last_delta=4, count=5)
        assert second.follows(first)

    def test_a_gap_means_it_does_not_follow(self):
        first = _header(base=100, last_delta=9)
        second = _header(base=115, last_delta=4, count=5)
        assert not second.follows(first)


class TestCoverage:
    def test_a_dense_batch_reports_no_gaps(self):
        assert "dense, no gaps" in _header(count=10, last_delta=9).coverage()

    def test_a_sparse_batch_reports_consumed_slots(self):
        note = _header(count=8, last_delta=9).coverage()
        assert "2 offset slot(s) consumed" in note

    def test_an_empty_batch_is_refused(self):
        with pytest.raises(Invalid):
            _header(count=0)
