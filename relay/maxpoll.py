"""Max poll interval: a live heartbeat is not the same as making progress.

A consumer has two ways to be broken, and the session timeout
catches only one. It can die, stopping its heartbeats, and the
group evicts it. Or it can livelock: its heartbeat thread keeps
beating while its processing thread is stuck on one poisoned
record, so the group believes it healthy while its partitions
make no progress, the quiet failure that is worse than a crash
because nothing alarms. The max-poll-interval closes the gap: a
consumer must not only heartbeat but also call poll within a
bound, and a consumer that heartbeats but has not polled past
the interval is evicted exactly as if it had died, because a
member holding partitions it is not advancing is worse than an
absent one, an absent member's partitions get reassigned while a
stuck member's are held hostage. The two timers measure two
different livenesses, connection and progress, and collapsing
them into one is how a stuck consumer keeps its partitions: it
answers the ping it can while failing the work it cannot.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class ConsumerHealth:
    instance_id: str
    last_heartbeat: int
    last_poll: int
    evicted: bool = False
    reason: str = ""


@dataclass
class ProgressTracker:
    session_timeout: int
    max_poll_interval: int
    consumers: dict[str, ConsumerHealth] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if self.max_poll_interval <= self.session_timeout:
            raise Invalid(
                "max-poll must exceed the session timeout, or "
                "the two livenesses collapse into one and a "
                "stuck consumer keeps its partitions"
            )

    def register(self, instance_id: str, now: int) -> None:
        self.consumers[instance_id] = ConsumerHealth(
            instance_id=instance_id,
            last_heartbeat=now,
            last_poll=now,
        )

    def heartbeat(self, instance_id: str, now: int) -> None:
        member = self._live(instance_id)
        member.last_heartbeat = now

    def poll(self, instance_id: str, now: int) -> None:
        member = self._live(instance_id)
        member.last_poll = now
        member.last_heartbeat = now

    def _live(self, instance_id: str) -> ConsumerHealth:
        member = self.consumers.get(instance_id)
        if member is None or member.evicted:
            raise Invalid(
                f"{instance_id} is not a live consumer"
            )
        return member

    def sweep(self, now: int) -> list[str]:
        evicted = []
        for member in self.consumers.values():
            if member.evicted:
                continue
            if now - member.last_heartbeat > self.session_timeout:
                member.evicted = True
                member.reason = "died (no heartbeat)"
                evicted.append(member.instance_id)
            elif now - member.last_poll > self.max_poll_interval:
                member.evicted = True
                member.reason = "livelocked (heartbeat but no poll)"
                evicted.append(member.instance_id)
        return sorted(evicted)

    def reason_for(self, instance_id: str) -> str:
        member = self.consumers.get(instance_id)
        if member is None:
            raise Invalid(f"{instance_id} is unknown")
        if not member.evicted:
            return f"{instance_id} is healthy"
        return f"{instance_id} evicted: {member.reason}"
