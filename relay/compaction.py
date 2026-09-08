"""Compaction: the log becomes a changelog, keeping the last word per key.

Time and size retention forget by age; compaction forgets by
redundancy. For a keyed topic where only the latest value per
key matters, a user's current address, a feature flag's current
state, compaction rewrites a sealed prefix keeping only the
last record for each key and discarding the superseded ones,
so a log of a million updates to a thousand keys compacts to a
thousand records. The rule that makes it safe is that
compaction preserves offsets: a kept record keeps its original
offset, gaps are legal, and a consumer reading through a
compacted region sees fewer records but never a wrong one. The
tombstone is the sharp edge: a record with a null value is a
delete marker, and compaction keeps it exactly long enough for
every consumer to observe the deletion, then removes it, because
a tombstone kept forever is a leak and a tombstone removed too
early resurrects the key for a lagging reader.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass(frozen=True)
class KeyedEntry:
    offset: int
    key: bytes
    value: bytes | None


@dataclass
class Compactor:
    tombstone_retention_ticks: int
    removed_superseded: int = 0
    tombstones_reaped: int = 0
    kept: list[KeyedEntry] = field(default_factory=list)

    def compact(
        self,
        entries: list[KeyedEntry],
        now: int,
        tombstone_ticks: dict[int, int],
        min_consumer_offset: int,
    ) -> list[KeyedEntry]:
        if not entries:
            raise Invalid("nothing to compact")
        last_offset_for_key: dict[bytes, int] = {}
        for entry in entries:
            last_offset_for_key[entry.key] = entry.offset
        result: list[KeyedEntry] = []
        for entry in entries:
            is_latest = (
                last_offset_for_key[entry.key] == entry.offset
            )
            if not is_latest:
                self.removed_superseded += 1
                continue
            if entry.value is None:
                born = tombstone_ticks.get(entry.offset, now)
                observed_by_all = (
                    entry.offset < min_consumer_offset
                )
                aged_out = (
                    now - born > self.tombstone_retention_ticks
                )
                if observed_by_all and aged_out:
                    self.tombstones_reaped += 1
                    continue
            result.append(entry)
        self.kept = result
        return result

    def preserves_offsets(
        self, kept: list[KeyedEntry]
    ) -> bool:
        offsets = [entry.offset for entry in kept]
        return offsets == sorted(offsets) and len(
            set(offsets)
        ) == len(offsets)

    def report(self, original_count: int) -> str:
        ratio = (
            original_count / len(self.kept)
            if self.kept
            else float("inf")
        )
        return (
            f"{original_count} records compact to "
            f"{len(self.kept)} ({ratio:.1f}x), "
            f"{self.removed_superseded} superseded removed, "
            f"{self.tombstones_reaped} tombstone(s) reaped "
            "after every consumer observed the delete"
        )
