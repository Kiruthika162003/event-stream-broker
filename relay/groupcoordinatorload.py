"""Coordinator load: a new coordinator replays offsets before it serves groups.

Consumer group state, who is in each group and where each group has
committed, lives in an internal log, a partition of the offsets topic,
and the coordinator for a group is the broker that leads that
partition. When that broker fails, leadership of the partition moves,
and the new leader becomes the coordinator, but it does not yet know
the group state, because that state is the contents of the log it has
just inherited and not yet read. Before it can answer where a group
left off or accept a new commit, it has to replay the partition from
the start into memory, rebuilding the in-memory view of every group
the partition holds. During that replay the coordinator is loading,
and the honest response to a group request is not a wrong answer from
half-built state but a coordinator-loading signal that tells the
client to back off and retry, the same way a client handles a
coordinator that moved. Serving a fetch of a committed offset from a
partially loaded state could hand back a stale or missing offset and
make a group reprocess or skip, so the load must finish first. The
loader tracks the log end it must reach and the offset it has replayed
to, advances as records are applied, and reports loading until the
replay catches up to the end, at which point it flips to loaded and
begins serving. It refuses to serve a group request while loading and
refuses to replay past the log end, because reading beyond what the
log holds would invent state. It reports the replay progress, the
fraction of the partition applied, because a coordinator stuck loading
is a group that cannot commit or fetch, an outage hiding as a slow
recovery."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class CoordinatorLoad:
    log_end: int
    replayed_to: int = 0

    def __post_init__(self) -> None:
        if self.log_end < 0:
            raise Invalid("the log end cannot be negative")

    def is_loaded(self) -> bool:
        return self.replayed_to >= self.log_end

    def apply(self, count: int) -> None:
        if count < 0:
            raise Invalid("cannot replay a negative number of records")
        if self.replayed_to + count > self.log_end:
            raise Invalid(
                f"replaying {count} would pass the log end {self.log_end}; "
                "reading beyond what the log holds would invent group state"
            )
        self.replayed_to += count

    def serve(self, request: str) -> str:
        if not self.is_loaded():
            raise Invalid(
                f"coordinator loading ({self.replayed_to}/{self.log_end}); "
                f"'{request}' gets a coordinator-loading signal to retry, not a "
                "wrong answer from half-built state"
            )
        return f"served '{request}' from loaded state"

    def progress(self) -> float:
        if self.log_end == 0:
            return 1.0
        return self.replayed_to / self.log_end

    def note(self) -> str:
        state = "loaded" if self.is_loaded() else "loading"
        return (
            f"{state}, replay {self.progress() * 100:.0f}% "
            f"({self.replayed_to}/{self.log_end}); a coordinator stuck loading "
            "is a group that cannot commit or fetch, an outage as slow recovery"
        )
