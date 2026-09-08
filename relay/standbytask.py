"""Standby task: keep a warm copy of another task's state so failover is quick.

A stream task's state store is rebuilt from its changelog when the
task moves to a new instance, and that rebuild takes as long as the
changelog is long, so a failover to a cold instance stalls
processing for the whole replay. A standby task removes that stall
by keeping a warm copy: one or more other instances run standby
tasks that consume the same changelog and apply it to a local
store continuously, so they hold a nearly-current copy of the state
without doing the active task's processing. When the active
instance fails, the work moves to whichever instance has a standby,
and instead of replaying the whole changelog it replays only the
small gap between the standby's position and the changelog end, so
recovery time drops from the whole log to the standby's lag. That
lag is the standby's value and its measure: a standby caught up to
within a few records fails over almost instantly, while one far
behind is barely better than cold. The manager picks, among the
instances holding a standby for a failed task, the one whose
standby has the least changelog lag, because promoting the least-
lagged standby means the shortest catch-up. It refuses to promote
an instance that holds no standby for the task, since that instance
would rebuild from cold and calling it a standby promotion would
hide the stall, and it refuses a standby whose lag exceeds the
whole changelog, an impossible reading that signals the standby's
position was never initialized. The report states the best
standby's lag as the expected failover replay, because that number,
not the changelog length, is what a failover will actually cost.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class StandbyManager:
    changelog_end: int
    standbys: dict[str, int] = field(default_factory=dict)

    def track(self, instance: str, standby_offset: int) -> None:
        if standby_offset > self.changelog_end:
            raise Invalid(
                f"standby offset {standby_offset} is past the "
                f"changelog end {self.changelog_end}; an impossible "
                "reading, the position was never initialized"
            )
        self.standbys[instance] = standby_offset

    def lag_of(self, instance: str) -> int:
        if instance not in self.standbys:
            raise Invalid(f"{instance} holds no standby for this task")
        return self.changelog_end - self.standbys[instance]

    def promote_best(self) -> str:
        if not self.standbys:
            raise Invalid(
                "no instance holds a standby; a promotion here would "
                "rebuild from cold and hide the stall"
            )
        best = min(self.standbys, key=self.lag_of)
        lag = self.lag_of(best)
        return (
            f"promote {best}: replays only {lag} record(s), not the "
            f"whole {self.changelog_end}; that lag is the failover cost"
        )

    def failover_cost(self) -> str:
        if not self.standbys:
            return "no standby; failover replays the whole changelog, cold"
        best_lag = min(self.lag_of(i) for i in self.standbys)
        return (
            f"best standby lag {best_lag}; that, not the changelog "
            "length, is what a failover will actually cost"
        )
