"""Static membership: a rolling restart should not rebalance the world.

Dynamic membership assigns each consumer a fresh id on connect,
so a consumer that restarts, during a deploy, a crash, a
routine bounce, looks like a departure followed by an arrival,
and the group rebalances twice for a member that was gone for
three seconds. During a rolling restart of fifty consumers that
is a hundred rebalances, and the group spends the deploy
thrashing instead of consuming. Static membership gives each
consumer a stable group-instance-id that survives restarts, so a
member that disconnects and reconnects within its session
timeout reclaims its exact previous partitions with no
rebalance at all. The safety condition is strict: reclaiming is
allowed only inside the session timeout, because a member gone
longer than that has genuinely died and its partitions were
rightly reassigned, so a late reclaim would be the same
double-ownership the whole protocol exists to prevent. The
report counts rebalances avoided, because the entire value of
static membership is a number that only shows up during a
deploy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class StaticMember:
    instance_id: str
    partitions: set[int]
    last_seen: int
    connected: bool = True


@dataclass
class StaticGroup:
    session_timeout: int
    members: dict[str, StaticMember] = field(default_factory=dict)
    rebalances_avoided: int = 0
    rebalances_forced: int = 0

    def __post_init__(self) -> None:
        if self.session_timeout < 1:
            raise Invalid("the session timeout must be positive")

    def join(
        self, instance_id: str, partitions: set[int], now: int
    ) -> str:
        self.members[instance_id] = StaticMember(
            instance_id=instance_id,
            partitions=set(partitions),
            last_seen=now,
        )
        return f"{instance_id} joined with {sorted(partitions)}"

    def disconnect(self, instance_id: str, now: int) -> None:
        member = self.members.get(instance_id)
        if member is None:
            raise Invalid(f"{instance_id} is not a member")
        member.connected = False
        member.last_seen = now

    def reconnect(self, instance_id: str, now: int) -> str:
        member = self.members.get(instance_id)
        if member is None:
            raise Invalid(
                f"{instance_id} has no static identity; it is a "
                "new member and must be assigned"
            )
        if now - member.last_seen > self.session_timeout:
            self.rebalances_forced += 1
            raise Invalid(
                f"{instance_id} was gone "
                f"{now - member.last_seen} ticks, past the "
                f"{self.session_timeout} timeout; it genuinely "
                "died and its partitions were reassigned, so a "
                "late reclaim is the double-ownership we prevent"
            )
        member.connected = True
        member.last_seen = now
        self.rebalances_avoided += 1
        return (
            f"{instance_id} reclaimed "
            f"{sorted(member.partitions)} with no rebalance"
        )

    def report(self) -> str:
        return (
            f"{self.rebalances_avoided} rebalance(s) avoided, "
            f"{self.rebalances_forced} forced; the avoided count "
            "is the whole value of static membership and it only "
            "shows up during a deploy"
        )
