"""Idle topics: quiet is not dead, and telling them apart saves the archive.

A cluster accumulates topics that were created for a project that
shipped, a test that ran once, a migration that finished, and
they sit there consuming metadata and operator attention forever.
Finding them to archive is easy to get wrong, because the signal
that looks obvious, no recent produces, is ambiguous: a topic
with no produces this week might be genuinely abandoned or might
be a low-frequency topic that fires monthly, a billing cycle, a
quarterly report, and archiving the latter breaks it the day it
was supposed to run. The detector uses two signals together, no
produces and no active consumers, over a window long enough to
outlast the topic's natural period, and even then it recommends
rather than acts, because the cost of archiving a live-but-slow
topic is an outage and the cost of keeping a dead one is a little
metadata. The recommendation states which signal is missing, so
an operator can judge: a topic with no produces but active
consumers is being drained, not abandoned, and one with produces
but no consumers is being written to by a producer whose reader
died, a different problem entirely. The safe recommendation is
mark-for-review, never auto-delete, because a detector confident
enough to delete on its own is a detector that will eventually
delete the quarterly report the week before it runs.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class TopicActivity:
    name: str
    last_produce_tick: int
    active_consumers: int


@dataclass
class IdleDetector:
    idle_window: int

    def __post_init__(self) -> None:
        if self.idle_window < 1:
            raise Invalid("the idle window must be positive")

    def assess(self, activity: TopicActivity, now: int) -> str:
        no_produces = (
            now - activity.last_produce_tick > self.idle_window
        )
        no_consumers = activity.active_consumers == 0
        if no_produces and no_consumers:
            return (
                f"{activity.name}: no produces and no consumers "
                "for the window; mark for review, never auto-"
                "delete, because a slow topic may fire monthly"
            )
        if no_produces and not no_consumers:
            return (
                f"{activity.name}: no produces but "
                f"{activity.active_consumers} active consumer(s); "
                "being drained, not abandoned"
            )
        if not no_produces and no_consumers:
            return (
                f"{activity.name}: produces but no consumers; a "
                "producer writing to a topic whose reader died, "
                "a different problem"
            )
        return f"{activity.name}: active on both signals"

    def archivable(
        self, activity: TopicActivity, now: int
    ) -> bool:
        return (
            now - activity.last_produce_tick > self.idle_window
            and activity.active_consumers == 0
        )
