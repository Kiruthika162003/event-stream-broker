"""Delete retention: a tombstone must outlive every consumer's chance to see it.

On a compacted topic a delete is a tombstone, a record with a
null value that says this key is gone, and compaction eventually
removes tombstones too, but removing one too soon is a specific
and nasty bug. A consumer rebuilding its state from the compacted
log needs to see the tombstone to learn the key was deleted; if
compaction removes the tombstone before that consumer reads past
it, the consumer sees the key's last real value and never learns
it was deleted, so its state keeps a key the log says is gone,
and the two disagree forever. Delete-retention is the minimum
time a tombstone is kept after it becomes eligible for
compaction, chosen to exceed the longest time a consumer might
take to read the log, so every consumer that will ever read past
the tombstone does so while it is still there. The tracker
enforces that a tombstone is removed only when both conditions
hold: it has aged past delete-retention, and every known consumer
has committed past its offset, because either alone is
insufficient, aged-but-unread strands a slow consumer and
read-but-not-aged risks a consumer nobody registered. The report
names the binding condition on a tombstone that cannot yet be
removed, because an operator wondering why compaction is not
reclaiming tombstones needs to know whether it is waiting on the
clock or on a consumer, and those have different remedies, raise
nothing versus find the stuck reader.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class Tombstone:
    key: bytes
    offset: int
    eligible_at: int


@dataclass
class DeleteRetention:
    retention_ticks: int

    def __post_init__(self) -> None:
        if self.retention_ticks < 1:
            raise Invalid("delete-retention must be positive")

    def removable(
        self,
        tombstone: Tombstone,
        now: int,
        min_consumer_offset: int,
    ) -> bool:
        aged = now - tombstone.eligible_at >= self.retention_ticks
        read = min_consumer_offset > tombstone.offset
        return aged and read

    def explain(
        self,
        tombstone: Tombstone,
        now: int,
        min_consumer_offset: int,
    ) -> str:
        aged = now - tombstone.eligible_at >= self.retention_ticks
        read = min_consumer_offset > tombstone.offset
        if aged and read:
            return (
                f"tombstone for {tombstone.key!r} removable: aged "
                "past retention and read by every consumer"
            )
        if not aged and not read:
            return (
                f"tombstone for {tombstone.key!r} held on both: "
                "still young and still unread by a consumer"
            )
        if not aged:
            return (
                f"tombstone for {tombstone.key!r} held on the "
                "clock; waiting out delete-retention, raise "
                "nothing"
            )
        return (
            f"tombstone for {tombstone.key!r} held on a reader; "
            "aged out but a consumer has not read past it, find "
            "the stuck reader"
        )
