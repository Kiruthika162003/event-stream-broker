"""Tombstone retention: keep a delete marker long enough for everyone to see it.

In a compacted topic a delete is a tombstone, a record with a key and a
null value that says this key is gone. Compaction keeps only the latest
record per key, so once a tombstone is the latest record for its key it
has done its job of erasing the older values, and it is tempting to
remove the tombstone itself in the very next compaction. That is a
mistake. A consumer that was offline, or is simply reading the log
slowly, needs to encounter the tombstone to learn the key was deleted;
if the tombstone were removed as soon as it compacted, that consumer
would see the old value, never see the delete, and keep a key its
upstream considers gone, a silent divergence between the log's state
and the consumers' state. So a tombstone is kept for a retention period
after it becomes eligible for deletion, delete.retention.ms, chosen to
exceed the longest a consumer might lag, and only after that grace does
compaction finally drop it. The tradeoff is direct: too short a
retention and a lagging consumer misses deletes, too long and deleted
keys linger in the log consuming space after they are logically gone.
The tracker marks a tombstone eligible at a time, decides whether it
may be removed at a later time given the retention, and computes the
deadline by which every consumer must have read past it. It refuses a
negative retention, because a delete grace cannot run backwards, and
reports whether a tombstone is still in its grace or past it, because a
tombstone removed early is a delete a slow consumer will never see, the
failure the retention exists to prevent."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class TombstoneRetention:
    retention_ms: int

    def __post_init__(self) -> None:
        if self.retention_ms < 0:
            raise Invalid("the delete grace cannot run backwards")

    def removal_deadline(self, eligible_at_ms: int) -> int:
        # the tombstone may not be removed until the grace elapses
        return eligible_at_ms + self.retention_ms

    def may_remove(self, eligible_at_ms: int, now_ms: int) -> bool:
        return now_ms >= self.removal_deadline(eligible_at_ms)

    def check_removal(self, eligible_at_ms: int, now_ms: int) -> str:
        deadline = self.removal_deadline(eligible_at_ms)
        if now_ms < deadline:
            raise Invalid(
                f"tombstone still in its grace until {deadline} (now {now_ms}); "
                "removing it early is a delete a slow consumer will never see"
            )
        return f"tombstone may be removed; grace elapsed at {deadline}"

    def note(self, eligible_at_ms: int, now_ms: int) -> str:
        deadline = self.removal_deadline(eligible_at_ms)
        state = "past grace" if now_ms >= deadline else "in grace"
        return (
            f"tombstone {state}, removable at {deadline}, now {now_ms}; too "
            "short and a lagging consumer misses the delete, too long and the "
            "key lingers after it is logically gone"
        )
