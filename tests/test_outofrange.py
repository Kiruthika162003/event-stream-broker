from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.outofrange import Window, resolve_out_of_range

WINDOW = Window(log_start=4200, log_end=9000)


class TestInRange:
    def test_an_in_range_offset_proceeds(self):
        assert "in range, fetch proceeds" in resolve_out_of_range(
            WINDOW, 5000, "earliest"
        )


class TestBelow:
    def test_below_with_earliest_resets_to_the_start(self):
        verdict = resolve_out_of_range(WINDOW, 100, "earliest")
        assert "reset to the log start 4200" in verdict

    def test_below_with_error_makes_loss_visible(self):
        verdict = resolve_out_of_range(WINDOW, 100, "error")
        assert "making the data loss visible" in verdict


class TestAbove:
    def test_above_the_end_refreshes_metadata(self):
        verdict = resolve_out_of_range(WINDOW, 99999, "earliest")
        assert "refresh metadata and re-find the leader" in verdict
        assert "truncation or a stale replica" in verdict

    def test_above_never_silently_resets(self):
        verdict = resolve_out_of_range(WINDOW, 99999, "error")
        # policy does not matter above the end
        assert "refresh metadata" in verdict


class TestRefusals:
    def test_an_inverted_window_is_refused(self):
        with pytest.raises(Invalid):
            Window(log_start=100, log_end=50)
