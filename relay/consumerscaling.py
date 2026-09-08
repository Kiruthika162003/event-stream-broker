"""Consumer scaling: a partition has one consumer, so partitions cap parallelism.

Within a consumer group a partition is owned by exactly one
consumer at a time, which is what gives a group its ordering and
its at-most-once ownership, and it has a consequence people hit
when they try to scale: a group can have at most as many actively
consuming members as the topic has partitions, and any members
beyond that sit idle, assigned nothing, consuming nothing, warm
spares that only take over if an active member leaves. So adding
consumers speeds a group up only until there is one per partition,
and past that point more consumers add cost without adding
throughput. To scale beyond the partition count the topic needs
more partitions, and that is not free: adding partitions changes
which partition a key hashes to, breaking the per-key ordering for
keys already in flight, so scaling a keyed topic by adding
partitions trades ordering for parallelism, a decision not to make
casually. The calculator computes, for a group size against a
partition count, how many consumers are active and how many idle,
and the maximum useful group size, which is the partition count. It
refuses a zero partition count, which supports no consumers at all,
and reports the idle consumers, because a group with idle members is
either over-provisioned, paying for consumers that do nothing, or
one partition short of using them, and the count says which. It
names that the way to use idle consumers is more partitions with
the ordering caveat, not more consumers, because a team adding
consumers to a maxed-out group is scaling the wrong dimension and
will see no improvement for the added cost."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class ConsumerScaling:
    partitions: int
    consumers: int

    def __post_init__(self) -> None:
        if self.partitions < 1:
            raise Invalid("a topic needs at least one partition")
        if self.consumers < 0:
            raise Invalid("consumer count cannot be negative")

    def active(self) -> int:
        return min(self.consumers, self.partitions)

    def idle(self) -> int:
        return max(0, self.consumers - self.partitions)

    def max_useful(self) -> int:
        return self.partitions

    def report(self) -> str:
        idle = self.idle()
        if idle == 0 and self.consumers < self.partitions:
            return (
                f"{self.consumers} active, room for "
                f"{self.partitions - self.consumers} more before the "
                "partition count caps parallelism"
            )
        if idle == 0:
            return f"{self.active()} active, one per partition, fully parallel"
        return (
            f"{self.active()} active, {idle} idle; to use the idle ones add "
            "partitions, not consumers, at the cost of keyed ordering, since "
            "more consumers on a maxed group add cost without throughput"
        )
