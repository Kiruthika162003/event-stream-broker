from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.purgatory import Purgatory


def purgatory() -> Purgatory:
    built = Purgatory()
    built.park("part-0", "req-a", threshold=100, deadline=50)
    built.park("part-0", "req-b", threshold=200, deadline=50)
    return built


class TestParking:
    def test_a_parked_request_waits(self):
        assert purgatory().pending() == 2

    def test_a_deadlineless_request_is_refused(self):
        with pytest.raises(Invalid) as caught:
            Purgatory().park("k", "r", threshold=1, deadline=0)
        assert "leak wearing a feature's clothes" in str(
            caught.value
        )


class TestEventCompletion:
    def test_progress_completes_satisfied_requests(self):
        built = purgatory()
        completed = built.on_progress("part-0", value=150)
        assert completed == ["req-a"]
        assert built.pending() == 1
        assert built.completed_by_event == 1

    def test_progress_can_complete_several_at_once(self):
        built = purgatory()
        completed = built.on_progress("part-0", value=250)
        assert completed == ["req-a", "req-b"]
        assert built.pending() == 0

    def test_progress_on_another_key_completes_nothing(self):
        built = purgatory()
        assert built.on_progress("part-9", value=999) == []


class TestTimeout:
    def test_the_deadline_completes_the_unsatisfied(self):
        built = purgatory()
        built.on_progress("part-0", value=150)
        timed_out = built.on_tick(now=50)
        assert timed_out == ["req-b"]
        assert built.completed_by_timeout == 1

    def test_a_satisfied_request_does_not_time_out(self):
        built = purgatory()
        built.on_progress("part-0", value=250)
        assert built.on_tick(now=100) == []


class TestTheReport:
    def test_the_report_separates_event_from_timeout(self):
        built = purgatory()
        built.on_progress("part-0", value=150)
        built.on_tick(now=50)
        report = built.report()
        assert "1 completed by event, 1 by timeout" in report
        assert "unmet conditions, not slow ones" in report
