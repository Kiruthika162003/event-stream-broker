"""An operations day: quotas, lag trends, rebalance, and the cleaner.

Run with: python -m examples.operationsday
"""

from __future__ import annotations

from relay.cooperative import CooperativeRebalance
from relay.lagmonitor import LagMonitor
from relay.logcleaner import DirtyLog, LogCleaner
from relay.quotas import ClientQuota


def morning_the_quota():
    quota = ClientQuota(
        client_id="ingest-fleet", bytes_per_tick=100, window_ticks=10
    )
    quota.record(now=1, size=600)
    verdict = quota.record(now=2, size=800)
    print(f"morning: {verdict.split(';')[0]}")


def midday_the_lag():
    monitor = LagMonitor()
    for tick, lag in [(0, 12000), (30, 9000), (60, 6000)]:
        monitor.observe(tick, lag)
    print(f"midday:  {monitor.verdict()}")


def afternoon_the_rebalance():
    rebalance = CooperativeRebalance(
        current={"c1": {0, 1, 2, 3}, "c2": {4, 5, 6, 7}},
        target={"c1": {0, 1}, "c2": {4, 5}, "c3": {2, 3, 6, 7}},
    )
    print(f"afternoon: {rebalance.revoke_phase()}")
    print(f"           {rebalance.assign_phase()}")


def evening_the_cleaner():
    cleaner = LogCleaner(min_dirty_ratio=0.3)
    logs = [
        DirtyLog(0, total_records=1000, superseded_records=900),
        DirtyLog(1, total_records=500, superseded_records=100),
    ]
    for log in cleaner.rank(logs):
        cleaner.clean(log)
    print(f"evening: {cleaner.efficiency().split(';')[0]}")


def main() -> int:
    morning_the_quota()
    midday_the_lag()
    afternoon_the_rebalance()
    evening_the_cleaner()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
