from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.hyperloglog import HyperLogLog


class TestDistinctCounting:
    def test_adding_the_same_item_twice_does_not_change_the_estimate(self):
        once = HyperLogLog(registers=64)
        once.add("x")
        many = HyperLogLog(registers=64)
        for _ in range(100):
            many.add("x")
        assert once.estimate() == many.estimate()

    def test_more_distinct_items_give_a_larger_estimate(self):
        small = HyperLogLog(registers=256)
        for i in range(10):
            small.add(f"k{i}")
        big = HyperLogLog(registers=256)
        for i in range(2000):
            big.add(f"k{i}")
        assert big.estimate() > small.estimate()

    def test_the_estimate_is_in_the_right_ballpark(self):
        hll = HyperLogLog(registers=256)
        for i in range(1000):
            hll.add(f"item-{i}")
        # approximate; allow a wide band around the true 1000
        assert 500 <= hll.estimate() <= 2000


class TestConfig:
    def test_a_non_power_of_two_register_count_is_refused(self):
        with pytest.raises(Invalid):
            HyperLogLog(registers=100)

    def test_a_zero_register_count_is_refused(self):
        with pytest.raises(Invalid):
            HyperLogLog(registers=0)


class TestErrorBound:
    def test_the_error_shrinks_with_more_registers(self):
        small = HyperLogLog(registers=16)
        big = HyperLogLog(registers=1024)
        small_rel = float(small.error_bound().split("~")[1].split("%")[0])
        big_rel = float(big.error_bound().split("~")[1].split("%")[0])
        assert big_rel < small_rel
