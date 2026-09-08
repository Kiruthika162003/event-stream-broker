from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.followerstale import FollowerRead


class TestStaleness:
    def test_staleness_is_the_watermark_gap(self):
        read = FollowerRead(
            leader_watermark=1000,
            follower_watermark=940,
            max_lag=100,
        )
        assert read.staleness() == 60

    def test_a_follower_ahead_of_the_leader_is_refused(self):
        with pytest.raises(Invalid) as caught:
            FollowerRead(
                leader_watermark=900,
                follower_watermark=950,
                max_lag=100,
            )
        assert "cannot be ahead" in str(caught.value)


class TestInSync:
    def test_within_max_lag_is_in_sync(self):
        read = FollowerRead(
            leader_watermark=1000,
            follower_watermark=940,
            max_lag=100,
        )
        assert read.in_sync()

    def test_past_max_lag_is_out_of_sync(self):
        read = FollowerRead(
            leader_watermark=1000,
            follower_watermark=850,
            max_lag=100,
        )
        assert not read.in_sync()


class TestMayServe:
    def test_a_tolerant_consumer_gets_the_follower(self):
        read = FollowerRead(
            leader_watermark=1000,
            follower_watermark=940,
            max_lag=100,
        )
        verdict = read.may_serve(tolerance=80)
        assert "follower read served: 60 stale" in verdict

    def test_a_strict_consumer_is_sent_to_the_leader(self):
        read = FollowerRead(
            leader_watermark=1000,
            follower_watermark=940,
            max_lag=100,
        )
        with pytest.raises(Invalid) as caught:
            read.may_serve(tolerance=30)
        assert "it must read the leader" in str(caught.value)

    def test_an_out_of_sync_follower_serves_nothing(self):
        read = FollowerRead(
            leader_watermark=1000,
            follower_watermark=850,
            max_lag=100,
        )
        with pytest.raises(Invalid) as caught:
            read.may_serve(tolerance=1000)
        assert "out of sync" in str(caught.value)
