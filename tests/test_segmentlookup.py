from __future__ import annotations

import pytest

from relay.errors import Missing
from relay.segmentlookup import SegmentSet


def _set():
    return SegmentSet(base_offsets=[0, 100, 200, 300], log_end=400)


class TestSegmentFor:
    def test_it_finds_the_floor_segment(self):
        assert _set().segment_for(150) == 100

    def test_an_exact_base_lands_in_its_own_segment(self):
        assert _set().segment_for(200) == 200

    def test_the_last_segment_holds_up_to_the_log_end(self):
        assert _set().segment_for(399) == 300

    def test_an_offset_below_the_log_start_is_gone(self):
        s = SegmentSet(base_offsets=[100, 200], log_end=300)
        with pytest.raises(Missing) as caught:
            s.segment_for(50)
        assert "deleted by retention" in str(caught.value)

    def test_an_offset_past_the_log_end_is_refused(self):
        with pytest.raises(Missing) as caught:
            _set().segment_for(400)
        assert "past the log end" in str(caught.value)


class TestLocality:
    def test_a_tail_read_lands_in_the_active_segment(self):
        note = _set().read_locality(350)
        assert "active segment" in note
        assert "being tailed" in note

    def test_a_historical_read_lands_in_an_old_segment(self):
        note = _set().read_locality(50)
        assert "old segment (base 0, 0 segment(s) before it)" in note
        assert "keeps old segments hot" in note

    def test_a_deeper_historical_read_counts_segments_before_it(self):
        note = _set().read_locality(250)
        assert "base 200, 2 segment(s) before it" in note
