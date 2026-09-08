"""Metadata snapshot: fold the old log into a state, replay only the tail.

The metadata log grows without bound as topics, partitions, and
configs change, and a broker joining or a controller failing over
must replay it to rebuild the cluster state, so an ever-growing log
means an ever-slower startup. A snapshot bounds that: the current
state is written out as of a particular offset, and everything in
the log at or below that offset can be discarded, because the
snapshot already contains its effect. A joiner then loads the
snapshot and replays only the tail, the records after the snapshot
offset, so replay time is bounded by how much changed since the
last snapshot rather than by the whole history. The saving is real
only if the snapshot offset advances: a snapshot taken and never
refreshed lets the tail grow until replay is slow again, so
snapshots are taken on an interval or a log-size trigger. The
manager refuses to load a snapshot against a log whose start is
already past the snapshot offset, because the records the snapshot
expected to still be replayable have been deleted and the state
would have a hole, and it refuses to discard log below a snapshot
that has not been durably written, because discarding the only
copy of records not yet folded into a persisted snapshot loses
them. The report states the tail length after a snapshot, because
the difference between a fresh snapshot with a short tail and a
stale one with a long tail is the difference between a fast
failover and a slow one.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class SnapshotManager:
    log_start: int = 0
    log_end: int = 0
    snapshot_offset: int = -1
    snapshot_durable: bool = False

    def take(self, at_offset: int) -> str:
        if at_offset > self.log_end:
            raise Invalid(
                f"cannot snapshot at {at_offset}; the log only "
                f"reaches {self.log_end}"
            )
        if at_offset <= self.snapshot_offset:
            raise Invalid(
                "a snapshot must advance; one that never refreshes "
                "lets the replay tail grow until startup is slow again"
            )
        self.snapshot_offset = at_offset
        self.snapshot_durable = False
        return f"snapshot taken at {at_offset}, not yet durable"

    def mark_durable(self) -> None:
        self.snapshot_durable = True

    def discard_below(self) -> str:
        if not self.snapshot_durable:
            raise Invalid(
                "refusing to discard log below a snapshot not yet "
                "durably written; that is the only copy of records "
                "not folded into a persisted snapshot"
            )
        self.log_start = self.snapshot_offset + 1
        return f"log below {self.log_start} discarded; folded into the snapshot"

    def replay_tail(self) -> int:
        if self.snapshot_offset < 0:
            return self.log_end - self.log_start
        return self.log_end - self.snapshot_offset

    def load(self) -> str:
        if self.snapshot_offset >= 0 and self.log_start > self.snapshot_offset + 1:
            raise Invalid(
                "the log start is past the snapshot offset; records "
                "the snapshot expected to replay are gone and the "
                "state would have a hole"
            )
        tail = self.replay_tail()
        return (
            f"loaded snapshot at {self.snapshot_offset}, replaying a "
            f"tail of {tail} record(s); a short tail is a fast "
            "failover, a long one a slow one"
        )
