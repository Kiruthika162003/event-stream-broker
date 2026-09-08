from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.listoffsets import OffsetQuery


class TestSymbolic:
    def test_earliest_is_the_log_start_not_zero(self):
        q = OffsetQuery(log_start=500, high_watermark=900, timestamped=True)
        assert q.earliest() == 500

    def test_latest_is_the_high_watermark(self):
        q = OffsetQuery(log_start=500, high_watermark=900, timestamped=True)
        assert q.latest() == 900

    def test_a_start_past_the_watermark_is_refused(self):
        with pytest.raises(Invalid):
            OffsetQuery(log_start=1000, high_watermark=900, timestamped=True)


class TestForTimestamp:
    def test_it_finds_the_first_record_at_or_after_the_target(self):
        q = OffsetQuery(log_start=0, high_watermark=100, timestamped=True)
        records = [(10, 1000), (11, 2000), (12, 3000)]
        offset, note = q.for_timestamp(2000, records)
        assert offset == 11
        assert "matched at offset 11" in note

    def test_no_match_resolves_to_the_high_watermark(self):
        q = OffsetQuery(log_start=0, high_watermark=100, timestamped=True)
        records = [(10, 1000), (11, 2000)]
        offset, note = q.for_timestamp(9999, records)
        assert offset == 100
        assert "start at the end" in note

    def test_a_timestamp_query_on_an_append_time_log_is_refused(self):
        q = OffsetQuery(log_start=0, high_watermark=100, timestamped=False)
        with pytest.raises(Invalid) as caught:
            q.for_timestamp(2000, [(10, 1000)])
        assert "broker append" in str(caught.value)
