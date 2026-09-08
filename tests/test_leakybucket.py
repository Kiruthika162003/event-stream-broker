from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.leakybucket import LeakyBucket


class TestOffer:
    def test_it_admits_up_to_capacity(self):
        b = LeakyBucket(capacity=100, drain_per_tick=1)
        assert "admitted 60" in b.offer(now=0, amount=60)
        assert "admitted 40" in b.offer(now=0, amount=40)

    def test_it_spills_a_burst_over_capacity(self):
        b = LeakyBucket(capacity=100, drain_per_tick=1)
        b.offer(now=0, amount=100)
        note = b.offer(now=0, amount=30)
        assert "spilled 30.0" in note
        assert b.spilled == 1


class TestDrain:
    def test_the_level_drains_over_time(self):
        b = LeakyBucket(capacity=100, drain_per_tick=1)
        b.offer(now=0, amount=100)
        # 50 ticks later, 50 drained, room for 50 more
        assert "admitted 50" in b.offer(now=50, amount=50)

    def test_a_backward_clock_is_refused(self):
        b = LeakyBucket(capacity=100, drain_per_tick=1)
        b.offer(now=50, amount=0)
        with pytest.raises(Invalid):
            b.offer(now=10, amount=0)


class TestConfig:
    def test_a_zero_capacity_is_refused(self):
        with pytest.raises(Invalid):
            LeakyBucket(capacity=0, drain_per_tick=1)

    def test_a_zero_drain_is_refused(self):
        with pytest.raises(Invalid):
            LeakyBucket(capacity=100, drain_per_tick=0)
