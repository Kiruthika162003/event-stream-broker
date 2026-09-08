from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.timestamptype import (
    CREATE_TIME,
    LOG_APPEND_TIME,
    TimestampChoice,
    retention_clock,
    suitable_for_event_time,
    switch_warning,
)


class TestRetentionClock:
    def test_create_time_ages_by_the_producer_clock(self):
        choice = TimestampChoice(CREATE_TIME)
        assert "producer's clock" in retention_clock(choice)
        assert "delete instantly or never" in retention_clock(choice)

    def test_log_append_time_is_immune_to_skew(self):
        choice = TimestampChoice(LOG_APPEND_TIME)
        assert "immune to producer skew" in retention_clock(choice)


class TestEventTime:
    def test_create_time_suits_event_time_windowing(self):
        choice = TimestampChoice(CREATE_TIME)
        assert "suitable for event-time windowing" in (
            suitable_for_event_time(choice)
        )

    def test_log_append_time_aggregates_the_wrong_axis(self):
        choice = TimestampChoice(LOG_APPEND_TIME)
        assert "aggregates the wrong axis" in (
            suitable_for_event_time(choice)
        )


class TestSwitching:
    def test_a_switch_warns_about_silent_query_change(self):
        warning = switch_warning(
            TimestampChoice(CREATE_TIME),
            TimestampChoice(LOG_APPEND_TIME),
        )
        assert "changes time-based query results with no error" in (
            warning
        )
        assert "nothing breaks" in warning

    def test_no_switch_is_no_change(self):
        assert switch_warning(
            TimestampChoice(CREATE_TIME),
            TimestampChoice(CREATE_TIME),
        ) == "no change"


class TestRefusals:
    def test_an_unknown_type_is_refused(self):
        with pytest.raises(Invalid):
            TimestampChoice("wall-clock-vibes")
