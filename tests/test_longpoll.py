from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.longpoll import LongPollRequest, resolve_fetch


def request() -> LongPollRequest:
    return LongPollRequest(min_bytes=100, max_wait=50, max_response=1000)


class TestResolution:
    def test_a_burst_returns_before_the_max_wait(self):
        accumulation = [(10, 50), (20, 150), (30, 300)]
        tick, note = resolve_fetch(request(), accumulation)
        assert tick == 20
        assert "does not wait out the timer" in note

    def test_an_idle_partition_returns_at_the_ceiling(self):
        accumulation = [(10, 10), (30, 20)]
        tick, note = resolve_fetch(request(), accumulation)
        assert tick == 50
        assert "without a busy-wait" in note
        assert "20 byte(s)" in note

    def test_data_exactly_at_min_bytes_returns(self):
        accumulation = [(15, 100)]
        tick, _ = resolve_fetch(request(), accumulation)
        assert tick == 15


class TestRefusals:
    def test_min_bytes_above_the_response_cap_is_refused(self):
        with pytest.raises(Invalid) as caught:
            LongPollRequest(
                min_bytes=2000, max_wait=50, max_response=1000
            )
        assert "maximum latency for minimum data" in str(
            caught.value
        )

    def test_a_zero_max_wait_is_refused(self):
        with pytest.raises(Invalid):
            LongPollRequest(min_bytes=10, max_wait=0, max_response=100)
