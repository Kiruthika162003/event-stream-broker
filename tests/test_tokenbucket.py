from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.tokenbucket import TokenBucket


class TestBurst:
    def test_a_full_bucket_serves_a_burst_up_to_capacity(self):
        b = TokenBucket(capacity=100, refill_per_tick=1)
        assert "served 100" in b.take(now=0, size=100)

    def test_once_drained_it_throttles(self):
        b = TokenBucket(capacity=100, refill_per_tick=1)
        b.take(now=0, size=100)
        note = b.take(now=0, size=10)
        assert "throttled 10" in note
        assert "wait ~10.0 tick(s)" in note


class TestRefill:
    def test_tokens_refill_with_elapsed_time(self):
        b = TokenBucket(capacity=100, refill_per_tick=1)
        b.take(now=0, size=100)
        # 50 ticks later, 50 tokens back.
        assert "served 50" in b.take(now=50, size=50)

    def test_refill_never_exceeds_capacity(self):
        b = TokenBucket(capacity=100, refill_per_tick=1)
        b.take(now=0, size=10)
        # idle a long time; bucket caps at capacity, not 90 + 10000.
        b.take(now=10000, size=0)
        assert b.tokens == 100

    def test_a_backwards_clock_is_refused(self):
        b = TokenBucket(capacity=100, refill_per_tick=1)
        b.take(now=50, size=0)
        with pytest.raises(Invalid):
            b.take(now=10, size=0)


class TestLimits:
    def test_a_request_larger_than_capacity_is_refused(self):
        b = TokenBucket(capacity=100, refill_per_tick=1)
        with pytest.raises(Invalid) as caught:
            b.take(now=0, size=200)
        assert "can never be satisfied" in str(caught.value)

    def test_a_bad_configuration_is_refused(self):
        with pytest.raises(Invalid):
            TokenBucket(capacity=0, refill_per_tick=1)
