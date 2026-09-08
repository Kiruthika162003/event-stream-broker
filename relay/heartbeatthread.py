"""Heartbeat thread: staying in the group is separate from making progress.

A consumer must do two things on a clock: heartbeat to prove it
is alive to the group, and make progress by polling and
processing records. Early consumer designs did both on one
thread, sending the heartbeat as a side effect of polling, and it
created a cruel failure: a consumer processing a large batch
slowly would not call poll, so it would not heartbeat, so the
group would declare it dead and rebalance its partitions away,
even though it was healthy and working hard. Separating the
heartbeat onto its own thread fixes the false death: the
heartbeat keeps proving liveness on its own clock while the
processor takes as long as it needs on a batch. But separation
introduces the opposite risk, a consumer that heartbeats forever
while its processor is wedged, alive to the group but making no
progress, holding partitions it is not advancing. So the design
keeps two independent timers with different meanings: the session
timeout, which the heartbeat thread satisfies and which detects a
truly dead consumer, and the max-poll-interval, which the poll
loop satisfies and which detects a live-but-stuck one. A consumer
is evicted if it fails either, and the tracker keeps them
distinct because they have different causes and fixes: a missed
heartbeat is a dead process or a network partition, while a
missed poll interval is a processor stuck on a record, and
conflating them sends the operator debugging the network when the
bug is a poison record wedging the processor.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class LivenessTimers:
    session_timeout: int
    max_poll_interval: int
    last_heartbeat: int = 0
    last_poll: int = 0

    def __post_init__(self) -> None:
        if self.session_timeout < 1 or self.max_poll_interval < 1:
            raise Invalid("both timers must be positive")

    def heartbeat(self, now: int) -> None:
        self.last_heartbeat = now

    def poll(self, now: int) -> None:
        self.last_poll = now
        self.last_heartbeat = now

    def evaluate(self, now: int) -> str:
        heartbeat_dead = (
            now - self.last_heartbeat > self.session_timeout
        )
        poll_stuck = (
            now - self.last_poll > self.max_poll_interval
        )
        if heartbeat_dead:
            return (
                "evicted on session timeout: a dead process or a "
                "network partition, not a stuck processor"
            )
        if poll_stuck:
            return (
                "evicted on max-poll-interval: alive to the group "
                "but the processor is wedged, likely a poison "
                "record, not a network problem"
            )
        return "healthy: heartbeating and making progress"
