from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.isolation import (
    READ_COMMITTED,
    READ_UNCOMMITTED,
    PartitionOffsets,
    readable_ceiling,
    uncommitted_gap,
)

OFFSETS = PartitionOffsets(high_watermark=1000, last_stable_offset=940)


class TestCeilings:
    def test_read_uncommitted_reaches_the_watermark(self):
        ceiling, note = readable_ceiling(READ_UNCOMMITTED, OFFSETS)
        assert ceiling == 1000
        assert "un-happened" in note

    def test_read_committed_stops_at_the_stable_offset(self):
        ceiling, note = readable_ceiling(READ_COMMITTED, OFFSETS)
        assert ceiling == 940
        assert "blocking behind a long-running open transaction" in (
            note
        )

    def test_an_unknown_level_is_refused(self):
        with pytest.raises(Invalid):
            readable_ceiling("read-vibes", OFFSETS)

    def test_stable_above_watermark_is_impossible(self):
        with pytest.raises(Invalid):
            PartitionOffsets(high_watermark=100, last_stable_offset=200)


class TestTheGap:
    def test_an_open_transaction_creates_a_gap(self):
        verdict = uncommitted_gap(OFFSETS)
        assert "60 record(s) are replicated but not stable" in (
            verdict
        )
        assert "the guarantee working, not a bug" in verdict

    def test_no_open_transaction_means_no_gap(self):
        clean = PartitionOffsets(
            high_watermark=1000, last_stable_offset=1000
        )
        assert "both levels read the same" in uncommitted_gap(clean)
