from __future__ import annotations

import pytest

from relay.errors import Invalid, Missing
from relay.followerfetch import (
    ReplicaEndpoint,
    select_replica,
    validate_follower_read,
)

LEADER = ReplicaEndpoint("b-a", "rack-a", high_watermark=1000, in_sync=True)
NEAR = ReplicaEndpoint("b-b", "rack-b", high_watermark=980, in_sync=True)
FAR = ReplicaEndpoint("b-c", "rack-c", high_watermark=999, in_sync=True)


class TestSelection:
    def test_a_same_rack_follower_is_preferred(self):
        replica, note = select_replica("rack-b", LEADER, [NEAR, FAR])
        assert replica.broker == "b-b"
        assert "trailing the leader by 20 record(s)" in note
        assert "stays a trade" in note

    def test_no_local_replica_falls_back_to_the_leader(self):
        replica, note = select_replica("rack-z", LEADER, [NEAR, FAR])
        assert replica is LEADER
        assert "paying cross-zone to stay current" in note

    def test_the_freshest_local_replica_wins(self):
        near2 = ReplicaEndpoint("b-b2", "rack-b", 990, in_sync=True)
        replica, _ = select_replica(
            "rack-b", LEADER, [NEAR, near2]
        )
        assert replica.broker == "b-b2"

    def test_an_out_of_sync_local_replica_is_skipped(self):
        stale = ReplicaEndpoint("b-b", "rack-b", 500, in_sync=False)
        replica, _ = select_replica("rack-b", LEADER, [stale])
        assert replica is LEADER


class TestSafeReads:
    def test_reading_at_the_follower_watermark_is_refused(self):
        with pytest.raises(Missing) as caught:
            validate_follower_read(NEAR, 980)
        assert "never the leader's" in str(caught.value)

    def test_reading_below_the_watermark_is_fine(self):
        validate_follower_read(NEAR, 979)

    def test_an_out_of_sync_replica_serves_nothing(self):
        stale = ReplicaEndpoint("b", "rack-b", 500, in_sync=False)
        with pytest.raises(Invalid):
            validate_follower_read(stale, 100)
