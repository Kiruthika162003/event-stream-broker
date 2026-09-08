from __future__ import annotations

import pytest

from relay.deadletter import RetryTracker
from relay.errors import Invalid


def tracker() -> RetryTracker:
    return RetryTracker(max_attempts=3)


class TestRetries:
    def test_failures_below_the_budget_retry(self):
        chosen = tracker()
        verdict = chosen.record_failure(
            "orders", 0, 42, "bad json"
        )
        assert "failed attempt 1 of 3" in verdict
        assert "will retry" in verdict

    def test_the_budget_exhausted_dead_letters(self):
        chosen = tracker()
        chosen.record_failure("orders", 0, 42, "bad json")
        chosen.record_failure("orders", 0, 42, "bad json")
        verdict = chosen.record_failure(
            "orders", 0, 42, "bad json"
        )
        assert "dead-lettered after 3 attempt(s)" in verdict
        assert "a ticket, not an outage" in verdict
        assert len(chosen.dead_letters) == 1

    def test_success_clears_the_attempt_count(self):
        chosen = tracker()
        chosen.record_failure("orders", 0, 42, "blip")
        chosen.record_success("orders", 0, 42)
        verdict = chosen.record_failure("orders", 0, 42, "blip")
        assert "attempt 1 of 3" in verdict

    def test_a_zero_budget_is_refused(self):
        with pytest.raises(Invalid):
            RetryTracker(max_attempts=0)


class TestProvenanceAndReplay:
    def test_the_dead_letter_carries_its_origin(self):
        chosen = tracker()
        for _ in range(3):
            chosen.record_failure("orders", 2, 99, "schema")
        letter = chosen.dead_letters[0]
        assert letter.source_topic == "orders"
        assert letter.source_partition == 2
        assert letter.source_offset == 99
        assert letter.attempts == 3

    def test_replay_removes_and_returns_the_letter(self):
        chosen = tracker()
        for _ in range(3):
            chosen.record_failure("orders", 0, 1, "bug")
        letter = chosen.replay(0)
        assert letter.source_offset == 1
        assert chosen.dead_letters == []

    def test_replaying_nothing_is_refused(self):
        with pytest.raises(Invalid):
            tracker().replay(0)


class TestTheReport:
    def test_an_empty_tracker_reports_a_home_for_all(self):
        assert tracker().report() == (
            "no dead letters; every record found a home"
        )

    def test_the_report_groups_by_reason(self):
        chosen = tracker()
        for offset in range(2):
            for _ in range(3):
                chosen.record_failure("orders", 0, offset, "bad json")
        for _ in range(3):
            chosen.record_failure("orders", 0, 9, "timeout")
        report = chosen.report()
        assert "2x bad json" in report
        assert "1x timeout" in report
        assert "a work queue" in report
