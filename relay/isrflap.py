"""ISR flapping: a replica oscillating in and out is worse than one that left.

A replica that drops out of the in-sync set and rejoins, over and
over, is a distinct pathology from one that simply falls behind
and stays out. Each transition is not free: dropping out shrinks
the in-sync set and may stall the watermark, rejoining triggers
work to verify it caught up, and a replica that does this every
few seconds keeps the partition in a churn that costs more than
if the replica had just left cleanly and stayed gone. The flap
detector tracks in-sync transitions over a window and flags a
replica whose transition count crosses a threshold, because the
transition rate, not the current state, is the signal: a replica
in-sync right now that flapped ten times this minute is less
trustworthy than one that has been steadily out for an hour, and
a monitor reading only the instantaneous state would call the
flapper healthy in the instant it happened to be in. The remedy
the detector recommends is deliberate and slightly harsh: a
confirmed flapper is held out of the in-sync set for a cool-down
even when it currently qualifies, because admitting it just to
watch it drop again trades a stable set for a churning one, and a
replica must prove sustained stability, not momentary
qualification, to rejoin. The report separates the flappers from
the cleanly-out, because they need different fixes, a flapper is
usually a sick disk or a saturated link while a clean departure
is usually a dead broker.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class ReplicaFlapHistory:
    name: str
    transitions: list[tuple[int, bool]] = field(
        default_factory=list
    )

    def record(self, tick: int, in_sync: bool) -> None:
        if self.transitions and tick <= self.transitions[-1][0]:
            raise Invalid("transitions must advance in time")
        if (
            not self.transitions
            or self.transitions[-1][1] != in_sync
        ):
            self.transitions.append((tick, in_sync))

    def transitions_in_window(
        self, now: int, window: int
    ) -> int:
        return sum(
            1
            for tick, _ in self.transitions
            if now - tick <= window
        )


@dataclass
class FlapDetector:
    window: int
    flap_threshold: int
    cooldown: int

    def __post_init__(self) -> None:
        if self.flap_threshold < 2:
            raise Invalid(
                "a flap needs at least two transitions"
            )

    def is_flapping(
        self, history: ReplicaFlapHistory, now: int
    ) -> bool:
        return (
            history.transitions_in_window(now, self.window)
            >= self.flap_threshold
        )

    def may_rejoin(
        self,
        history: ReplicaFlapHistory,
        now: int,
        currently_qualifies: bool,
    ) -> str:
        if not currently_qualifies:
            return f"{history.name} does not currently qualify"
        if self.is_flapping(history, now):
            return (
                f"{history.name} held out for cool-down: it "
                "qualifies now but flapped past the threshold, "
                "and admitting it trades a stable set for a "
                "churning one"
            )
        return (
            f"{history.name} may rejoin: qualifies and has been "
            "stable, not momentarily qualified"
        )

    def classify(
        self,
        histories: list[ReplicaFlapHistory],
        now: int,
    ) -> str:
        flappers = [
            h.name
            for h in histories
            if self.is_flapping(h, now)
        ]
        if not flappers:
            return "no flappers; out-of-sync replicas left cleanly"
        return (
            f"{len(flappers)} flapper(s) ({', '.join(sorted(flappers))}): "
            "usually a sick disk or saturated link, a different "
            "fix from a clean departure's dead broker"
        )
