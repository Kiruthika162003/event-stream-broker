"""Snapshot install: catch up a follower the log can no longer catch up.

A follower normally catches up by fetching the log entries it is
missing and applying them, but that only works while the leader
still has those entries. A follower that fell far behind, a new
replica, or one that was down through a compaction, may need
entries the leader has already discarded, so replaying from the log
is impossible: the entries are gone. The leader catches it up a
different way, by sending a snapshot, the state as of an offset,
which the follower installs wholesale and then resumes fetching the
log from that offset forward. The choice between replay and
snapshot is about how far behind the follower is against what the
leader retains: if the follower's position is still within the
retained log, replay is cheaper, sending only the missing entries;
if it is before the log start, replay cannot work and a snapshot is
the only way. The snapshot is usually larger than the few entries a
slightly-behind follower needs, so it is the fallback for the
far-behind case, not the default. The installer decides replay
versus snapshot from the follower's position against the leader's
log start, installs a snapshot by replacing the follower's state
and setting its position to the snapshot offset, and refuses to
install a snapshot older than the follower already has, which would
move it backwards and lose state it had caught up on. It refuses a
snapshot whose offset is past the leader's own log end, an
impossible snapshot of state that does not exist. It reports which
mechanism a given lag calls for, because a follower always needing
a snapshot is one that keeps falling behind the log retention, a
sign retention is too short or the follower too slow to keep up."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

REPLAY = "replay"
SNAPSHOT = "snapshot"


@dataclass
class SnapshotInstaller:
    log_start: int
    log_end: int
    follower_position: int = 0

    def __post_init__(self) -> None:
        if self.log_start > self.log_end:
            raise Invalid("log start cannot exceed log end")

    def mechanism(self) -> str:
        if self.follower_position < self.log_start:
            return SNAPSHOT
        return REPLAY

    def install(self, snapshot_offset: int) -> str:
        if snapshot_offset > self.log_end:
            raise Invalid(
                f"snapshot offset {snapshot_offset} is past the log end "
                f"{self.log_end}; a snapshot of state that does not exist"
            )
        if snapshot_offset <= self.follower_position:
            raise Invalid(
                f"snapshot offset {snapshot_offset} is not past the follower's "
                f"position {self.follower_position}; installing it would move "
                "the follower backwards and lose caught-up state"
            )
        self.follower_position = snapshot_offset
        return f"snapshot installed at {snapshot_offset}; resume fetching from there"

    def report(self) -> str:
        mech = self.mechanism()
        if mech == SNAPSHOT:
            behind = self.log_start - self.follower_position
            return (
                f"follower {behind} before the log start; the entries it needs "
                "are compacted away, so a snapshot, not replay; always needing "
                "one means retention is too short or the follower too slow"
            )
        missing = self.log_end - self.follower_position
        return (
            f"follower within the retained log; replay the {missing} missing "
            "entry(ies), cheaper than a snapshot"
        )
