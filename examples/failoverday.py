"""A failover day: the leader dies, a follower rises, the log stays honest.

Run with: python -m examples.failoverday
"""

from __future__ import annotations

from relay.election import Candidate, PartitionElector
from relay.recovery import EpochMarker, RecoveryPlan
from relay.replication import ReplicaState, ReplicationSet


def morning_the_watermark():
    repl = ReplicationSet(
        leader="b1",
        followers={
            "b2": ReplicaState("b2", fetched_offset=980),
            "b3": ReplicaState("b3", fetched_offset=1000),
        },
        min_in_sync=2,
        max_lag=50,
        leader_end_offset=1000,
    )
    print(f"morning: committed through {repl.committable_watermark() - 1}")
    print(f"         {repl.pace_report()}")


def noon_the_leader_dies():
    elector = PartitionElector(epoch=7, committed_offset=980)
    result = elector.elect(
        [
            Candidate("b2", log_end_offset=980, in_sync=True),
            Candidate("b3", log_end_offset=1000, in_sync=True),
        ]
    )
    print(
        f"noon:    {result.leader} elected at epoch "
        f"{result.epoch}; {result.truncation_note}"
    )


def afternoon_the_old_leader_returns():
    leader_epochs = [
        EpochMarker(6, 0),
        EpochMarker(7, 500),
        EpochMarker(8, 1000),
    ]
    plan = RecoveryPlan(
        local_end=1040,
        local_epochs=[EpochMarker(6, 0), EpochMarker(7, 500)],
    )
    verdict = plan.recover(leader_epochs, leader_end=1000)
    print(f"afternoon: {verdict}")


def main() -> int:
    morning_the_watermark()
    noon_the_leader_dies()
    afternoon_the_old_leader_returns()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
