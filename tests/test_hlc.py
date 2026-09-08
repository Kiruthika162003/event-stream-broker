from __future__ import annotations

from relay.hlc import HybridLogicalClock


class TestTick:
    def test_advancing_wall_time_resets_the_counter(self):
        c = HybridLogicalClock()
        assert c.tick(10) == (10, 0)
        assert c.tick(20) == (20, 0)

    def test_a_stalled_clock_bumps_the_counter(self):
        c = HybridLogicalClock()
        c.tick(10)
        assert c.tick(10) == (10, 1)
        assert c.tick(10) == (10, 2)

    def test_a_backward_clock_still_advances_via_the_counter(self):
        c = HybridLogicalClock()
        c.tick(10)
        assert c.tick(5) == (10, 1)


class TestReceive:
    def test_a_receive_stamps_after_the_send(self):
        c = HybridLogicalClock(physical=10, counter=0)
        stamp = c.on_receive(wall_now=10, msg=(15, 3))
        assert stamp == (15, 4)
        assert HybridLogicalClock.compare(stamp, (15, 3)) == 1

    def test_a_receive_ahead_of_everything_resets_the_counter(self):
        c = HybridLogicalClock(physical=10, counter=5)
        stamp = c.on_receive(wall_now=30, msg=(20, 2))
        assert stamp == (30, 0)


class TestCompareAndDrift:
    def test_compare_is_physical_then_counter(self):
        assert HybridLogicalClock.compare((10, 0), (10, 1)) == -1
        assert HybridLogicalClock.compare((11, 0), (10, 9)) == 1
        assert HybridLogicalClock.compare((5, 2), (5, 2)) == 0

    def test_a_growing_counter_flags_skew(self):
        c = HybridLogicalClock()
        c.tick(10)
        c.tick(10)
        assert "skew" in c.drift_note(wall_now=10)
