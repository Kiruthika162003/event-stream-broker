"""Group max size: cap members, because a rebalance's cost grows with them.

A consumer group can only usefully have as many active members as
the topic has partitions, since a member beyond that count sits
idle with no partition to own, so a group with a thousand members
on a fifty-partition topic has nine hundred fifty idle consumers
doing nothing but making every rebalance slower, because a
rebalance must coordinate with every member whether or not it
will receive a partition. Worse, the idle members are usually a
bug, a client that leaks consumers, spawning a new one per request
without closing the old, and the group silently absorbs them
until a rebalance takes minutes and the whole group stalls on the
coordination. The size cap turns that silent degradation into an
explicit rejection: a group at its member cap refuses a new
member with the count named, so the leaking client gets an error
that points at its own leak instead of slowly poisoning the
group. The cap is set relative to the partition count, because
the useful ceiling is the partition count plus a small standby
margin for fast failover, and a cap far above that admits idle
members that only cost rebalance time. The limiter reports the
utilization, members against partitions, because a group at
twenty percent utilization has four idle members for every
working one, a signal of a leak or an over-provisioned deployment
that the cap has not yet caught but soon will.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class GroupSizeLimiter:
    partition_count: int
    standby_margin: int
    members: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.partition_count < 1 or self.standby_margin < 0:
            raise Invalid(
                "partition count positive, margin nonnegative"
            )

    def cap(self) -> int:
        return self.partition_count + self.standby_margin

    def join(self, member: str) -> str:
        if member in self.members:
            return f"{member} already a member"
        if len(self.members) >= self.cap():
            raise Invalid(
                f"group at its cap of {self.cap()} "
                f"({self.partition_count} partitions + "
                f"{self.standby_margin} standby); a member beyond "
                "the partition count sits idle and only slows "
                "rebalances, so this points at a leaking client"
            )
        self.members.add(member)
        return f"{member} joined ({len(self.members)}/{self.cap()})"

    def leave(self, member: str) -> None:
        self.members.discard(member)

    def utilization(self) -> str:
        working = min(len(self.members), self.partition_count)
        idle = max(0, len(self.members) - self.partition_count)
        pct = 100 * working // max(len(self.members), 1)
        note = (
            "; idle members per working one signal a leak or "
            "over-provisioning the cap will soon catch"
            if idle > working
            else ""
        )
        return (
            f"{len(self.members)} member(s), {working} working, "
            f"{idle} idle ({pct}% utilization){note}"
        )
