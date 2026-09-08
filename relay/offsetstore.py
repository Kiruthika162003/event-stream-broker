"""The offset store: committed positions are records in a compacted log.

Where does a consumer group's committed offset actually live?
The elegant answer this broker uses is that it lives in the log
itself: commits are records in an internal compacted topic keyed
by group and partition, so the machinery that stores user data,
append, replicate, compact, is the same machinery that stores
consumer progress, and there is no second durability story to
get wrong. Compaction keeps only the latest commit per key, so
the store's size is bounded by the number of group-partition
pairs, not the number of commits ever made, which is why a group
committing every second for a year does not grow the store
without bound. A commit is only durable once its record is
committed in the underlying log, which means offset commits
inherit the same replication guarantees as data: a group's
progress survives exactly the failures its data survives, no
more and no less, and that symmetry is the point, because a
broker where data is replicated but progress is not loses its
consumers' places on the very failure the replication was meant
to survive.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid, Missing


@dataclass(frozen=True)
class CommitKey:
    group: str
    topic: str
    partition: int


@dataclass
class OffsetStore:
    commits: dict[CommitKey, int] = field(default_factory=dict)
    commit_records_written: int = 0

    def commit(
        self, key: CommitKey, offset: int, durable: bool
    ) -> str:
        if not durable:
            raise Invalid(
                "an offset commit is durable only once its "
                "record is committed in the underlying log; "
                "acknowledging early loses progress on the very "
                "failure replication was meant to survive"
            )
        held = self.commits.get(key)
        if held is not None and offset < held:
            raise Invalid(
                f"commit {offset} is behind the stored {held}; "
                "committed offsets move forward"
            )
        self.commits[key] = offset
        self.commit_records_written += 1
        return (
            f"{key.group}/{key.topic}-{key.partition} committed "
            f"at {offset}"
        )

    def fetch(self, key: CommitKey) -> int:
        offset = self.commits.get(key)
        if offset is None:
            raise Missing(
                f"no committed offset for "
                f"{key.group}/{key.topic}-{key.partition}"
            )
        return offset

    def compacted_size(self) -> int:
        return len(self.commits)

    def bound_report(self) -> str:
        return (
            f"{self.commit_records_written} commit record(s) "
            f"written, {self.compacted_size()} survive "
            "compaction; the store is bounded by group-partition "
            "pairs, not by commits ever made"
        )
