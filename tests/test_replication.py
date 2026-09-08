from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.replication import ReplicaState, ReplicationSet


def repl_set(**overrides) -> ReplicationSet:
    settings = {
        "leader": "leader",
        "followers": {
            "f1": ReplicaState("f1", fetched_offset=100),
            "f2": ReplicaState("f2", fetched_offset=95),
        },
        "min_in_sync": 2,
        "max_lag": 50,
        "leader_end_offset": 100,
    }
    settings.update(overrides)
    return ReplicationSet(**settings)


class TestTheWatermark:
    def test_the_committed_offset_is_the_slowest_replica(self):
        assert repl_set().committable_watermark() == 95

    def test_the_leader_alone_would_commit_its_own_end(self):
        alone = repl_set(followers={}, min_in_sync=1)
        assert alone.committable_watermark() == 100

    def test_below_the_floor_the_broker_refuses_to_commit(self):
        starved = repl_set(
            followers={
                "f1": ReplicaState("f1", 100, in_sync=False),
                "f2": ReplicaState("f2", 95, in_sync=False),
            }
        )
        with pytest.raises(Invalid) as caught:
            starved.committable_watermark()
        assert "chooses unavailability" in str(caught.value)


class TestEviction:
    def test_a_slow_follower_leaves_the_in_sync_set(self):
        chosen = repl_set(
            followers={
                "f1": ReplicaState("f1", fetched_offset=100),
                "slow": ReplicaState("slow", fetched_offset=10),
            }
        )
        evicted = chosen.evict_laggards()
        assert evicted == ["slow"]
        assert chosen.in_sync_count() == 2

    def test_eviction_unfreezes_the_watermark(self):
        chosen = repl_set(
            min_in_sync=2,
            followers={
                "f1": ReplicaState("f1", fetched_offset=100),
                "slow": ReplicaState("slow", fetched_offset=10),
            },
        )
        chosen.evict_laggards()
        assert chosen.committable_watermark() == 100

    def test_a_bad_floor_is_refused(self):
        with pytest.raises(Invalid):
            repl_set(min_in_sync=0)


class TestThePaceReport:
    def test_the_report_names_the_pace_setter(self):
        report = repl_set().pace_report()
        assert "pace-setter f2 at 95 (5 behind the leader)" in (
            report
        )
