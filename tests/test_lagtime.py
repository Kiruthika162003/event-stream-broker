from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.lagtime import LagReading


class TestLags:
    def test_offset_lag_is_the_record_gap(self):
        r = LagReading(
            end_offset=10000,
            consumed_offset=5000,
            end_timestamp=9000,
            consumed_timestamp=9000,
        )
        assert r.offset_lag() == 5000

    def test_time_lag_is_the_timestamp_gap(self):
        r = LagReading(
            end_offset=10000,
            consumed_offset=5000,
            end_timestamp=9000,
            consumed_timestamp=6000,
        )
        assert r.time_lag() == 3000


class TestRefusals:
    def test_a_consumer_past_the_end_is_refused(self):
        with pytest.raises(Invalid):
            LagReading(
                end_offset=100,
                consumed_offset=200,
                end_timestamp=9000,
                consumed_timestamp=9000,
            )

    def test_a_consumed_timestamp_ahead_of_the_end_is_refused(self):
        with pytest.raises(Invalid) as caught:
            LagReading(
                end_offset=100,
                consumed_offset=50,
                end_timestamp=9000,
                consumed_timestamp=9500,
            )
        assert "ahead of the present" in str(caught.value)


class TestRecencyNote:
    def test_high_offset_lag_low_time_lag_is_named(self):
        r = LagReading(
            end_offset=10000,
            consumed_offset=5000,
            end_timestamp=9000,
            consumed_timestamp=9000,
        )
        note = r.recency_note()
        assert "behind on volume, current on recency" in note

    def test_both_growing_is_reported_together(self):
        r = LagReading(
            end_offset=10000,
            consumed_offset=5000,
            end_timestamp=9000,
            consumed_timestamp=3000,
        )
        note = r.recency_note()
        assert "5000 record(s) and 6000 time unit(s) behind" in note
