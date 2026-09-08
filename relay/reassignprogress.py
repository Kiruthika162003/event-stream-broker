"""Reassignment progress: is this partition move advancing, or wedged.

Moving a partition to a new broker means the new replica fetches
the entire partition from the leader to catch up before it can
join the in-sync set, and for a large partition that takes a long
time, during which the only honest question is whether it is
making progress or stuck. A reassignment that is advancing, the
new replica's offset climbing toward the leader's, needs only
patience; one that is wedged, the offset flat while the leader's
grows, needs intervention, and telling them apart from a single
snapshot is impossible, because a snapshot shows a gap without
showing whether the gap is closing. The tracker samples the new
replica's offset over time and computes closure velocity, the
rate at which the remaining gap shrinks, and from it an ETA, so
the operator learns not just that the move is 60 percent done but
that it will finish in twenty minutes or never. The never case is
the one the tracker exists to catch: a closure velocity at or
below zero means the new replica is falling behind as fast as it
catches up, usually because the reassignment's fetch is throttled
below the partition's write rate, so the move can never complete
and the throttle must be raised or the writes slowed. The tracker
refuses to report an ETA from a single sample, because an ETA
without a velocity is a guess, and a guess presented as an ETA is
worse than no ETA at all, since the operator acts on it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class ReassignmentTracker:
    target_offset: int
    samples: list[tuple[int, int]] = field(default_factory=list)

    def observe(
        self, tick: int, replica_offset: int, leader_offset: int
    ) -> None:
        if self.samples and tick <= self.samples[-1][0]:
            raise Invalid("samples must advance in time")
        self.target_offset = leader_offset
        self.samples.append((tick, replica_offset))

    def closure_velocity(self) -> float:
        if len(self.samples) < 2:
            raise Invalid(
                "an ETA needs a velocity, and a velocity needs "
                "two samples; a guess presented as an ETA is "
                "worse than none"
            )
        (t0, o0), (t1, o1) = self.samples[0], self.samples[-1]
        return (o1 - o0) / (t1 - t0)

    def eta(self) -> str:
        velocity = self.closure_velocity()
        gap = self.target_offset - self.samples[-1][1]
        if velocity <= 0:
            return (
                "WEDGED: closure velocity is zero or negative, the "
                "new replica falls behind as fast as it catches "
                "up; raise the reassignment throttle or slow the "
                "writes, because this move can never complete"
            )
        if gap <= 0:
            return "complete: the new replica has caught the leader"
        ticks = int(gap / velocity)
        return (
            f"advancing: {gap} record(s) left at {velocity:.1f}/"
            f"tick, about {ticks} tick(s) to complete; patience, "
            "not intervention"
        )
