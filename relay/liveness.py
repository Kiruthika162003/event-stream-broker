"""Liveness: a member is alive until its silence outlasts its lease.

A consumer group must notice a dead member fast enough to
reassign its partitions, and slow enough not to evict a member
that was merely busy for a moment. The heartbeat is the signal:
each member renews before its session timeout, and a member
whose last heartbeat is older than the timeout is presumed dead
and its partitions are freed for rebalancing. The trap the
tracker refuses to fall into is the pause that looks like a
death: a long garbage-collection stall or a slow poll can
silence a healthy member, so eviction is a decision with a
timestamp attached and a member that heartbeats after eviction
is told it was fenced, not welcomed back into its old
assignment, because a member that believes it still owns
partitions a reassignment already moved is two consumers
processing one partition, the split brain of the consumer side.
The report separates suspected from confirmed, since a broker
that treats every hiccup as a death rebalances itself to a
standstill.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Fenced, Invalid


@dataclass
class Member:
    name: str
    last_heartbeat: int
    generation: int
    evicted: bool = False


@dataclass
class LivenessTracker:
    session_timeout: int
    members: dict[str, Member] = field(default_factory=dict)
    generation: int = 0
    evictions: int = 0

    def __post_init__(self) -> None:
        if self.session_timeout < 1:
            raise Invalid("the session timeout must be positive")

    def join(self, name: str, now: int) -> str:
        self.generation += 1
        self.members[name] = Member(
            name=name,
            last_heartbeat=now,
            generation=self.generation,
        )
        return f"{name} joined at generation {self.generation}"

    def heartbeat(self, name: str, now: int) -> str:
        member = self.members.get(name)
        if member is None:
            raise Invalid(f"{name} is not a member")
        if member.evicted:
            raise Fenced(
                f"{name} was evicted and its partitions moved; "
                "heartbeating now would make two consumers own "
                "one partition, so it must rejoin, not resume"
            )
        member.last_heartbeat = now
        return f"{name} renewed at {now}"

    def sweep(self, now: int) -> list[str]:
        newly_dead = []
        for member in self.members.values():
            if member.evicted:
                continue
            if now - member.last_heartbeat > self.session_timeout:
                member.evicted = True
                self.evictions += 1
                newly_dead.append(member.name)
        if newly_dead:
            self.generation += 1
        return sorted(newly_dead)

    def live_members(self) -> list[str]:
        return sorted(
            name
            for name, member in self.members.items()
            if not member.evicted
        )

    def status(self, now: int) -> str:
        suspected = [
            member.name
            for member in self.members.values()
            if not member.evicted
            and now - member.last_heartbeat
            > self.session_timeout // 2
        ]
        return (
            f"{len(self.live_members())} live, "
            f"{len(suspected)} suspected (silent past half the "
            f"timeout), {self.evictions} evicted; a broker that "
            "treats every hiccup as death rebalances to a "
            "standstill"
        )
