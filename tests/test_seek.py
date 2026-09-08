from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.seek import (
    LogBounds,
    seek_to_beginning,
    seek_to_end,
    seek_to_offset,
)

BOUNDS = LogBounds(log_start=4200, high_watermark=9000)


class TestSeekToOffset:
    def test_a_valid_offset_positions_exactly(self):
        offset, note = seek_to_offset(BOUNDS, 5000)
        assert offset == 5000
        assert "as requested" in note

    def test_below_the_start_clamps_up(self):
        offset, note = seek_to_offset(BOUNDS, 100)
        assert offset == 4200
        assert "would skip intended records" in note

    def test_past_the_watermark_clamps_down(self):
        offset, note = seek_to_offset(BOUNDS, 99999)
        assert offset == 9000
        assert "blocks forever on records that do not exist" in note


class TestNamedSeeks:
    def test_seek_to_beginning_lands_on_the_start(self):
        offset, note = seek_to_beginning(BOUNDS)
        assert offset == 4200
        assert "cannot be stale" in note

    def test_seek_to_end_lands_on_the_watermark(self):
        offset, note = seek_to_end(BOUNDS)
        assert offset == 9000
        assert "never a stale number" in note


class TestRefusals:
    def test_inverted_bounds_are_refused(self):
        with pytest.raises(Invalid):
            LogBounds(log_start=100, high_watermark=50)
