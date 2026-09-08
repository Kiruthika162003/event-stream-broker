"""Rebalance storm: one flapping member can rebalance the group to a standstill.

A rebalance is disruptive, so a group that rebalances constantly
does little else, and the usual cause is a single flapping member:
one consumer that joins, times out, gets removed, rejoins, and
triggers a rebalance each time, dragging the whole group through a
stop-the-world pause on its cycle. The group as a whole looks
broken, endless rebalances, while the fault is one member. The
detector counts rebalances in a trailing window and, when the rate
crosses a threshold, looks for the member responsible: the one that
has joined and left most often, because a healthy member joins once
and stays while a flapping one churns. Naming that member is most
of the fix, because the remedy, restart it, fix its network, raise
its session timeout, is applied to it, not to the group. The
dampener goes further and can quarantine a member that has flapped
past a limit, holding it out of the group for a cool-off so the
remaining members reach a stable assignment instead of being
rebalanced by the flapper on every cycle, trading that member's
partitions being unowned briefly for the group making progress at
all. The detector refuses to quarantine the last stable member,
because holding it out would leave the group empty and consume
nothing, worse than tolerating the flap, and it refuses a window or
threshold of zero, which would flag every rebalance as a storm. The
report states the rebalance rate against the threshold and names
the churn leader, because a storm caught early and traced to one
member is a restart, while one left to run is a backlog that grows
for as long as the group cannot settle.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class StormDetector:
    window: int
    threshold: int
    rebalances: list[int] = field(default_factory=list)
    churn: dict[str, int] = field(default_factory=dict)
    stable_members: int = 0

    def __post_init__(self) -> None:
        if self.window < 1 or self.threshold < 1:
            raise Invalid("window and threshold must be positive")

    def record_rebalance(self, now: int, culprit: str) -> None:
        self.rebalances.append(now)
        self.rebalances = [t for t in self.rebalances if now - t < self.window]
        self.churn[culprit] = self.churn.get(culprit, 0) + 1

    def is_storm(self) -> bool:
        return len(self.rebalances) >= self.threshold

    def churn_leader(self) -> str:
        if not self.churn:
            raise Invalid("no rebalances recorded")
        return max(self.churn, key=self.churn.get)

    def may_quarantine(self, member: str, flap_limit: int) -> str:
        if self.churn.get(member, 0) < flap_limit:
            raise Invalid(
                f"{member} has flapped {self.churn.get(member, 0)} time(s), "
                f"under the limit {flap_limit}; not yet the culprit"
            )
        if self.stable_members <= 1:
            raise Invalid(
                "refusing to quarantine the last stable member; an empty "
                "group consumes nothing, worse than tolerating the flap"
            )
        return (
            f"quarantine {member} for a cool-off; the group settles "
            "instead of being rebalanced by the flapper each cycle"
        )

    def report(self) -> str:
        rate = len(self.rebalances)
        verdict = "STORM" if self.is_storm() else "steady"
        leader = self.churn_leader() if self.churn else "none"
        return (
            f"{rate} rebalance(s) in the window vs threshold "
            f"{self.threshold}: {verdict}; churn leader '{leader}', the "
            "member to restart before the backlog grows"
        )
