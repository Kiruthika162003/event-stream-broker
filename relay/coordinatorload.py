"""Coordinator load: a new coordinator must replay its state before it serves.

When the offsets partition that backs a group moves to a new
broker, that broker becomes the group's coordinator, but it does
not yet hold the group's state, which lives in the partition's log
as a history of commit and membership records. Before it can answer
a single request the new coordinator must replay that log from the
start, rebuilding the committed offset for each partition and the
current membership, because answering a fetch-offset request
mid-replay could return an offset it has not yet read past and so
report a stale or missing commit. During replay the coordinator
rejects requests with a load-in-progress signal, telling clients to
retry rather than trust an answer, and this is a deliberate
unavailability: a group whose coordinator just moved is briefly
unable to commit or join until replay finishes, and the duration is
proportional to the offsets partition's size, which is why a
bloated offsets partition makes coordinator failover slow. The
loader tracks progress as offsets replayed against the partition's
end, so an operator watching a slow failover can see how far the
replay has to go rather than only that it is not done. The loader
refuses to mark itself ready before it has replayed to the end,
because a coordinator that starts serving early serves from a
partial view, and it refuses to serve at all while loading, because
the whole point of the load is that its answers are not yet
trustworthy. The report states the fraction replayed, because
during an incident the difference between nearly-loaded and barely-
started decides whether to wait or to intervene.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class CoordinatorLoad:
    partition_end: int
    replayed_to: int = 0
    ready: bool = False

    def __post_init__(self) -> None:
        if self.partition_end < 0:
            raise Invalid("the partition end cannot be negative")

    def replay(self, up_to: int) -> None:
        if up_to < self.replayed_to:
            raise Invalid(
                "replay cannot go backwards; the log is read "
                "forward from the start"
            )
        self.replayed_to = min(up_to, self.partition_end)

    def mark_ready(self) -> str:
        if self.replayed_to < self.partition_end:
            raise Invalid(
                f"replayed only to {self.replayed_to} of "
                f"{self.partition_end}; a coordinator that serves "
                "before the end serves from a partial view"
            )
        self.ready = True
        return "coordinator ready; state fully replayed"

    def serve(self, request: str) -> str:
        if not self.ready:
            raise Invalid(
                f"load in progress ({self.fraction()}); '{request}' "
                "must retry, because a mid-replay answer is not yet "
                "trustworthy"
            )
        return f"served '{request}'"

    def fraction(self) -> str:
        if self.partition_end == 0:
            return "100% of 0"
        pct = self.replayed_to / self.partition_end * 100
        return f"{pct:.0f}% ({self.replayed_to}/{self.partition_end})"
