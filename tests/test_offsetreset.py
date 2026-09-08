from __future__ import annotations

import pytest

from relay.errors import Invalid, Lagging
from relay.offsetreset import (
    PartitionBounds,
    ResetLedger,
    resolve_reset,
)

BOUNDS = PartitionBounds(first_offset=4200, high_watermark=9000)


class TestValidOffsets:
    def test_a_valid_committed_offset_is_left_alone(self):
        offset, note = resolve_reset("latest", 5000, BOUNDS)
        assert offset == 5000
        assert "still valid" in note

    def test_an_unknown_policy_is_refused(self):
        with pytest.raises(Invalid):
            resolve_reset("vibes", None, BOUNDS)


class TestNewConsumer:
    def test_earliest_replays_the_retained_log(self):
        offset, note = resolve_reset("earliest", None, BOUNDS)
        assert offset == 4200
        assert "new consumer" in note
        assert "replaying the retained log" in note

    def test_latest_skips_to_the_end(self):
        offset, note = resolve_reset("latest", None, BOUNDS)
        assert offset == 9000
        assert "skipping what was missed" in note

    def test_error_refuses_to_choose(self):
        with pytest.raises(Lagging) as caught:
            resolve_reset("error", None, BOUNDS)
        assert "loses data for half its consumers" in str(
            caught.value
        )


class TestFellBehind:
    def test_a_stale_offset_below_the_window_resets(self):
        offset, note = resolve_reset("earliest", 100, BOUNDS)
        assert offset == 4200
        assert "consumer fell behind" in note

    def test_latest_on_a_lagging_consumer_skips_the_gap(self):
        offset, note = resolve_reset("latest", 100, BOUNDS)
        assert offset == 9000
        assert "fell behind" in note


class TestTheLedger:
    def test_the_two_reset_kinds_are_counted_apart(self):
        ledger = ResetLedger()
        _, a = resolve_reset("latest", None, BOUNDS)
        _, b = resolve_reset("latest", 100, BOUNDS)
        ledger.record(a)
        ledger.record(b)
        report = ledger.report()
        assert "1 new-consumer reset(s), 1 fell-behind reset(s)" in (
            report
        )
        assert "never nothing" in report
