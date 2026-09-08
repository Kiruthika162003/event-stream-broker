from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.eventtime import DROP, FAIL, USE_ARRIVAL, EventTimeExtractor


class TestExtract:
    def test_it_extracts_the_field(self):
        e = EventTimeExtractor(field_name="ts", fallback=USE_ARRIVAL)
        assert e.extract({"ts": 5000}, arrival_time=9000) == 5000

    def test_a_missing_field_uses_arrival_time(self):
        e = EventTimeExtractor(field_name="ts", fallback=USE_ARRIVAL)
        assert e.extract({}, arrival_time=9000) == 9000
        assert e.fell_back == 1

    def test_a_missing_field_drops_under_drop_policy(self):
        e = EventTimeExtractor(field_name="ts", fallback=DROP)
        assert e.extract({}, arrival_time=9000) is None

    def test_a_missing_field_fails_under_fail_policy(self):
        e = EventTimeExtractor(field_name="ts", fallback=FAIL)
        with pytest.raises(Invalid) as caught:
            e.extract({}, arrival_time=9000)
        assert "stream stops" in str(caught.value)

    def test_an_absurd_timestamp_is_refused(self):
        e = EventTimeExtractor(field_name="ts", fallback=USE_ARRIVAL)
        with pytest.raises(Invalid) as caught:
            e.extract({"ts": -5}, arrival_time=9000)
        assert "corrupts the window" in str(caught.value)


class TestConfig:
    def test_an_unknown_policy_is_refused(self):
        with pytest.raises(Invalid):
            EventTimeExtractor(field_name="ts", fallback="guess")


class TestFallbackNote:
    def test_it_reports_the_fallback_rate(self):
        e = EventTimeExtractor(field_name="ts", fallback=USE_ARRIVAL)
        e.extract({}, arrival_time=1)
        e.extract({"ts": 2}, arrival_time=1)
        note = e.fallback_note(total=2)
        assert "1/2 record(s) fell back (50%)" in note
