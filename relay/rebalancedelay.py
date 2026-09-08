"""Rebalance delay: wait a moment so a fleet starting together joins once.

When a consumer group with many members deploys, the members do not
start at the same instant, they come up over a few seconds, and a
coordinator that rebalanced on each arrival would run a rebalance
per member: the first joins and gets everything, the second joins
and triggers a reassignment, the third another, so a group of ten
starting up suffers ten rebalances, each a stop-the-world pause,
before it settles. The initial rebalance delay avoids the herd: when
the first member joins an empty group, the coordinator does not
rebalance immediately, it waits a short delay for more members to
arrive, and each new member that joins within the delay extends it
a little, up to a cap, so the group waits until arrivals quiet down
and then rebalances once with everyone present. The result is one
rebalance at startup instead of one per member, trading a few
seconds of initial delay for avoiding a burst of pauses, which is
the right trade because the members were not doing useful work
during startup anyway. The delay is bounded by a maximum so a
steady trickle of joiners cannot extend it forever, and past the
maximum the coordinator rebalances with who it has and folds later
arrivals into a subsequent rebalance. The scheduler starts the delay
on the first join, extends it on each join within the window up to
the cap, and reports whether it is still collecting or ready to
rebalance. It refuses a negative delay or cap, and a cap below the
base delay, which would cap the delay shorter than its own start. It
reports how many members were batched into the one rebalance,
because a large batch is the herd the delay just prevented, the
pauses it saved."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class RebalanceDelay:
    base_delay: int
    max_delay: int
    started_at: int = -1
    ready_at: int = -1
    batched: int = 0

    def __post_init__(self) -> None:
        if self.base_delay < 0 or self.max_delay < 0:
            raise Invalid("delays cannot be negative")
        if self.max_delay < self.base_delay:
            raise Invalid("the max delay cannot be below the base delay")

    def on_join(self, now: int) -> str:
        if self.started_at < 0:
            self.started_at = now
            self.ready_at = now + self.base_delay
            self.batched = 1
            return f"first join; collecting until {self.ready_at}"
        self.batched += 1
        extended = min(now + self.base_delay, self.started_at + self.max_delay)
        self.ready_at = max(self.ready_at, extended)
        return f"joined, {self.batched} batched; collecting until {self.ready_at}"

    def ready(self, now: int) -> bool:
        return self.started_at >= 0 and now >= self.ready_at

    def status(self, now: int) -> str:
        if self.started_at < 0:
            return "empty group; no rebalance pending"
        if self.ready(now):
            return (
                f"ready: rebalancing once with {self.batched} member(s) "
                "batched, the herd of per-member rebalances prevented"
            )
        return f"collecting {self.batched} member(s), rebalance at {self.ready_at}"
