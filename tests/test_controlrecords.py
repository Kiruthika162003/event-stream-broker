from __future__ import annotations

import pytest

from relay.controlrecords import (
    ControlAudience,
    LogEntry,
    consumer_visible,
    next_data_offset,
    offsets_stay_dense,
)
from relay.errors import Invalid


def mixed_log() -> list[LogEntry]:
    return [
        LogEntry(0, "data", b"a"),
        LogEntry(1, "data", b"b"),
        LogEntry(2, "commit", None),
        LogEntry(3, "data", b"c"),
    ]


class TestFiltering:
    def test_control_records_are_hidden_from_consumers(self):
        visible = consumer_visible(mixed_log())
        assert [e.offset for e in visible] == [0, 1, 3]

    def test_control_records_still_hold_their_offset(self):
        assert offsets_stay_dense(mixed_log())

    def test_the_next_data_offset_skips_control(self):
        assert next_data_offset(mixed_log(), after=1) == 3

    def test_no_data_after_only_control_is_refused(self):
        entries = [
            LogEntry(0, "data", b"a"),
            LogEntry(1, "abort", None),
        ]
        with pytest.raises(Invalid) as caught:
            next_data_offset(entries, after=0)
        assert "consumers never receive" in str(caught.value)


class TestAudiences:
    def test_the_data_path_sees_only_data(self):
        report = ControlAudience().for_data_path(mixed_log())
        assert "3 data record(s) to the consumer" in report
        assert "1 control record(s) filtered out" in report
        assert "no consumer drifts" in report

    def test_the_admin_path_sees_the_markers(self):
        markers = ControlAudience().for_admin(mixed_log())
        assert markers == ["offset 2: commit marker"]

    def test_a_control_entry_is_recognized(self):
        assert LogEntry(0, "commit", None).is_control()
        assert not LogEntry(0, "data", b"x").is_control()
