"""Producer snapshot: rebuild the dedup state from a snapshot, not the whole log.

On recovery the broker must rebuild, per producer id, the last
sequence number it accepted, because that map is what lets it keep
rejecting duplicates after a restart, and without it a producer's
first retried batch after recovery would be appended twice.
Rebuilding the map by replaying every batch in the log is correct
but slow, so the broker snapshots the producer state at each
segment boundary: a small file listing each active producer id, its
last sequence, and the first offset of any transaction it has open.
On recovery it loads the most recent snapshot whose offset is at or
below the recovered log end and replays only the batches after it,
so recovery time is bounded by one segment's worth of records
rather than the whole log. The open-transaction offset in the
snapshot matters: a producer mid-transaction at the snapshot point
has records that an abort must later skip, and losing that offset
would leave the aborted records unmarked. The loader refuses a
snapshot taken past the recovered log end, because the log was
truncated below it during recovery and the snapshot describes
producer state for records that no longer exist. It also refuses to
apply a snapshot sequence that goes backwards for a producer id
already loaded from a later snapshot, because the newest snapshot
holds the truth and an older one must not overwrite it. The report
states how many batches the snapshot saved replaying, because a
snapshot taken too rarely leaves a long tail and recovery is slow
again, the same failure the snapshot was meant to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass(frozen=True)
class ProducerEntry:
    producer_id: int
    last_seq: int
    open_txn_first_offset: int = -1


@dataclass
class ProducerSnapshot:
    offset: int
    entries: list[ProducerEntry] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.offset < 0:
            raise Invalid("a snapshot offset cannot be negative")


@dataclass
class SnapshotLoader:
    recovered_log_end: int
    state: dict[int, ProducerEntry] = field(default_factory=dict)
    loaded_from: int = -1

    def load(self, snapshot: ProducerSnapshot) -> str:
        if snapshot.offset > self.recovered_log_end:
            raise Invalid(
                f"snapshot at {snapshot.offset} is past the "
                f"recovered log end {self.recovered_log_end}; the "
                "log was truncated below it and it describes records "
                "that no longer exist"
            )
        if snapshot.offset < self.loaded_from:
            raise Invalid(
                "an older snapshot cannot overwrite state already "
                "loaded from a newer one; the newest holds the truth"
            )
        for entry in snapshot.entries:
            self.state[entry.producer_id] = entry
        self.loaded_from = snapshot.offset
        return f"loaded {len(snapshot.entries)} producer(s) at {snapshot.offset}"

    def tail_to_replay(self) -> int:
        if self.loaded_from < 0:
            return self.recovered_log_end
        return self.recovered_log_end - self.loaded_from

    def open_transactions(self) -> list[int]:
        return [
            e.producer_id
            for e in self.state.values()
            if e.open_txn_first_offset >= 0
        ]

    def savings(self) -> str:
        tail = self.tail_to_replay()
        return (
            f"replaying a tail of {tail} record(s) instead of the "
            f"whole {self.recovered_log_end}; a snapshot taken too "
            "rarely leaves a long tail and recovery is slow again"
        )
