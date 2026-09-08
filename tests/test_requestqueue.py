from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.requestqueue import RequestQueue


def queue() -> RequestQueue:
    return RequestQueue(capacity=3)


class TestShedding:
    def test_requests_enqueue_until_full(self):
        q = queue()
        for number in range(3):
            assert "enqueued" in q.offer(f"r{number}", False)

    def test_a_full_queue_sheds_immediately(self):
        q = queue()
        for number in range(3):
            q.offer(f"r{number}", False)
        verdict = q.offer("overflow", False)
        assert "shed: queue full at 3" in verdict
        assert "after its caller gave up" in verdict
        assert q.shed == 1

    def test_a_zero_capacity_queue_is_refused(self):
        with pytest.raises(Invalid):
            RequestQueue(capacity=0)


class TestControlPriority:
    def test_control_jumps_ahead_of_data(self):
        q = queue()
        q.offer("produce", False)
        q.offer("leader-change", True)
        assert q.next_request() == "leader-change"
        assert q.next_request() == "produce"

    def test_control_is_never_shed(self):
        q = queue()
        for number in range(3):
            q.offer(f"r{number}", False)
        verdict = q.offer("urgent-control", True)
        assert "control" in verdict
        assert q.shed == 0

    def test_an_empty_queue_has_no_next(self):
        with pytest.raises(Invalid):
            queue().next_request()


class TestTheReport:
    def test_the_report_separates_shed_from_control(self):
        q = queue()
        for number in range(3):
            q.offer(f"r{number}", False)
        q.offer("overflow", False)
        q.offer("ctl", True)
        report = q.report()
        assert "1 control ahead" in report
        assert "1 shed under load" in report
        assert "optimized the wrong thing" in report
