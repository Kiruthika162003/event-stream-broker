"""A rebalance day: members join, the leader assigns, a newcomer restarts it.

Run with: python -m examples.rebalanceday
"""

from __future__ import annotations

from relay.eagerrebalance import EagerRebalance
from relay.heartbeatsignal import HeartbeatCoordinator
from relay.joingroup import JoinPhase
from relay.syncgroup import SyncPhase


def morning_the_group_forms():
    join = JoinPhase(generation=1)
    join.join("c1", ["cooperative-sticky", "range"])
    join.join("c2", ["range"])
    print(f"morning: {join.close_window()}")
    return join


def noon_the_leader_assigns(join: JoinPhase):
    sync = SyncPhase(leader=join.leader(), members=set(join.members))
    sync.submit(join.leader(), {"c1": [0, 1], "c2": [2, 3]})
    print(f"noon:    c2 gets {sync.slice_for('c2')}; {sync.shares()}")


def afternoon_a_newcomer_triggers_a_rebalance():
    coord = HeartbeatCoordinator(generation=1)
    coord.register("c1")
    coord.register("c2")
    print(f"afternoon: stable heartbeat -> {coord.heartbeat('c1', 1)}")
    coord.start_rebalance()
    print(f"           newcomer joined -> {coord.heartbeat('c1', 1)}")


def evening_count_the_eager_cost():
    eager = EagerRebalance(total_partitions=4, moved_partitions=1)
    print(f"evening: {eager.report()}")


def main() -> int:
    join = morning_the_group_forms()
    noon_the_leader_assigns(join)
    afternoon_a_newcomer_triggers_a_rebalance()
    evening_count_the_eager_cost()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
