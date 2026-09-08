from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.fetching import FetchRequest, plan_fetch


def request(**overrides) -> FetchRequest:
    settings = {
        "min_bytes": 100,
        "max_bytes": 1000,
        "max_wait_ticks": 50,
    }
    settings.update(overrides)
    return FetchRequest(**settings)


class TestTheContract:
    def test_min_bytes_reached_sends_immediately(self):
        result = plan_fetch(request(), [60, 60], now_wait=0)
        assert result.bytes_returned == 120
        assert "min-bytes reached" in result.reason

    def test_max_wait_expired_sends_a_partial_batch(self):
        result = plan_fetch(request(), [30], now_wait=50)
        assert result.records_returned == 1
        assert "max-wait" in result.reason
        assert "never hangs" in result.reason

    def test_still_waiting_returns_nothing_with_patience_left(self):
        result = plan_fetch(request(), [30], now_wait=10)
        assert result.records_returned == 0
        assert "40 tick(s) of patience left" in result.reason

    def test_max_bytes_caps_the_batch(self):
        result = plan_fetch(
            request(min_bytes=200, max_bytes=200),
            [80, 80, 80, 80],
            now_wait=50,
        )
        assert result.bytes_returned <= 200
        assert result.records_returned == 2


class TestAwkwardRecords:
    def test_an_oversized_record_is_returned_alone(self):
        result = plan_fetch(
            request(max_bytes=100), [500], now_wait=0
        )
        assert result.records_returned == 1
        assert "beats deadlock on principle" in result.reason


class TestRefusals:
    def test_min_above_max_is_refused(self):
        with pytest.raises(Invalid):
            FetchRequest(min_bytes=500, max_bytes=100, max_wait_ticks=1)

    def test_negative_wait_is_refused(self):
        with pytest.raises(Invalid):
            FetchRequest(min_bytes=1, max_bytes=10, max_wait_ticks=-1)
