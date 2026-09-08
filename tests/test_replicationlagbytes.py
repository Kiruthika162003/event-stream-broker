from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.replicationlagbytes import ByteLag


class TestLag:
    def test_lag_is_the_byte_gap(self):
        b = ByteLag(
            leader_bytes=10000,
            follower_bytes=6000,
            bandwidth_per_tick=100,
            write_rate_per_tick=50,
        )
        assert b.lag_bytes() == 4000

    def test_a_follower_ahead_is_refused(self):
        with pytest.raises(Invalid):
            ByteLag(
                leader_bytes=100,
                follower_bytes=200,
                bandwidth_per_tick=10,
                write_rate_per_tick=1,
            )


class TestCatchUp:
    def test_it_catches_up_when_bandwidth_beats_writes(self):
        b = ByteLag(
            leader_bytes=10000,
            follower_bytes=6000,
            bandwidth_per_tick=100,
            write_rate_per_tick=50,
        )
        # net 50/tick, 4000 lag -> ~80 ticks
        assert "catches up in ~80 tick(s)" in b.report()
        assert not b.falling_behind()

    def test_it_falls_behind_when_writes_meet_bandwidth(self):
        b = ByteLag(
            leader_bytes=10000,
            follower_bytes=6000,
            bandwidth_per_tick=50,
            write_rate_per_tick=50,
        )
        assert b.falling_behind()
        assert "never catches up" in b.report()


class TestConfig:
    def test_zero_bandwidth_is_refused(self):
        with pytest.raises(Invalid):
            ByteLag(
                leader_bytes=100,
                follower_bytes=0,
                bandwidth_per_tick=0,
                write_rate_per_tick=0,
            )
