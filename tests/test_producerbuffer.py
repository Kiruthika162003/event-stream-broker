from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.producerbuffer import ProducerBuffer


def blocking() -> ProducerBuffer:
    return ProducerBuffer(
        capacity_bytes=1000, on_full="block", block_timeout=50
    )


def failing() -> ProducerBuffer:
    return ProducerBuffer(
        capacity_bytes=1000, on_full="fail", block_timeout=50
    )


class TestBuffering:
    def test_records_buffer_until_full(self):
        buf = blocking()
        assert "buffered 600 bytes" in buf.append(600, 0)
        assert buf.used_bytes == 600

    def test_a_silent_drop_policy_is_refused(self):
        with pytest.raises(Invalid) as caught:
            ProducerBuffer(1000, on_full="drop", block_timeout=1)
        assert "invisible data loss" in str(caught.value)


class TestFailPolicy:
    def test_fail_returns_immediately_on_full(self):
        buf = failing()
        buf.append(900, 0)
        verdict = buf.append(200, 0)
        assert "would rather drop than stall" in verdict
        assert buf.failed_sends == 1


class TestBlockPolicy:
    def test_block_waits_then_buffers(self):
        buf = blocking()
        buf.append(900, 0)
        verdict = buf.append(200, free_in_ticks=10)
        assert "blocked 10 tick(s) then buffered" in verdict
        assert buf.ticks_blocked == 10

    def test_block_has_a_timeout(self):
        buf = blocking()
        buf.append(900, 0)
        verdict = buf.append(200, free_in_ticks=100)
        assert "even the patient policy has a bound" in verdict
        assert buf.failed_sends == 1


class TestTheReport:
    def test_the_report_names_time_blocked_as_capacity_signal(self):
        buf = blocking()
        buf.append(900, 0)
        buf.append(200, free_in_ticks=10)
        report = buf.report()
        assert "10 tick(s) blocked" in report
        assert "capacity signal the buffer sees first" in report

    def test_freeing_makes_room(self):
        buf = blocking()
        buf.append(900, 0)
        buf.free(500)
        assert "buffered 400 bytes" in buf.append(400, 0)
