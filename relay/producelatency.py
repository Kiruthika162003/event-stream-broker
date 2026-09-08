"""Produce latency: where the milliseconds go, and why acks decides which dominate.

A produce request's latency is not one number but a sum of stages,
and knowing which stage dominates is what tells an operator where
to look when produce is slow. The stages are: time queued on the
broker's request queue before a handler picks it up, time to append
the batch to the leader's log, and, when the producer waits for
replication, time for the in-sync followers to fetch and
acknowledge the batch. The acks mode decides which stages count.
Acks-leader returns after the append, so its latency is queue plus
append and nothing else, fast and independent of the followers.
Acks-all waits for the slowest in-sync follower to acknowledge, so
its latency adds the replication wait, which is bounded by the
slowest follower's fetch, not the average, because the batch is
committed only when the last required follower has it. This is why
one slow follower raises produce latency for acks-all producers
across every partition it follows, even though the leader and the
other followers are fast: the slowest link sets the commit time.
The model computes the expected latency for a given acks mode from
the stage times, using the slowest follower for the replication
wait rather than the mean, because the mean would understate the
tail that acks-all actually experiences. It refuses a negative
stage time, and it names the dominant stage, because a produce slow
on the queue points at an overloaded broker shedding nothing while
one slow on replication points at a lagging follower, two different
fixes. The report states the breakdown so a latency number becomes
a diagnosis rather than just a symptom.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class ProduceLatency:
    queue_ms: float
    append_ms: float
    follower_acks_ms: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.queue_ms < 0 or self.append_ms < 0:
            raise Invalid("stage times cannot be negative")
        if any(t < 0 for t in self.follower_acks_ms):
            raise Invalid("a follower ack time cannot be negative")

    def replication_wait(self) -> float:
        # bounded by the slowest in-sync follower, not the mean
        return max(self.follower_acks_ms, default=0.0)

    def latency(self, acks_all: bool) -> float:
        base = self.queue_ms + self.append_ms
        if acks_all:
            return base + self.replication_wait()
        return base

    def dominant_stage(self, acks_all: bool) -> str:
        stages = {"queue": self.queue_ms, "append": self.append_ms}
        if acks_all:
            stages["replication"] = self.replication_wait()
        top = max(stages, key=stages.get)
        hints = {
            "queue": "an overloaded broker",
            "append": "slow disk or large batches",
            "replication": "a lagging follower",
        }
        return f"{top} dominates ({stages[top]:.1f}ms), pointing at {hints[top]}"

    def report(self, acks_all: bool) -> str:
        total = self.latency(acks_all)
        mode = "acks=all" if acks_all else "acks=leader"
        return (
            f"{mode} latency {total:.1f}ms; {self.dominant_stage(acks_all)}; "
            "the slowest follower, not the average, sets the commit time"
        )
