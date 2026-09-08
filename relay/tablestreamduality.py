"""Table-stream duality: a table is a folded stream, a stream is a table's log.

A table and a stream are two views of the same thing. A stream is a
sequence of updates, each an independent fact that happened, and
folding a stream by key, keeping the latest value for each, gives a
table, the current state. Going the other way, a table's history of
changes is itself a stream, the changelog, where each record is an
update to a key, so the table and its changelog are duals: fold the
changelog and you get the table back, and read the table's updates
in order and you get the changelog. This duality is why a compacted
topic can back a table, the compacted topic keeps the latest value
per key, exactly the table, while its full history before
compaction is the changelog stream. The conversions make the
duality concrete. Stream-to-table folds updates, applying each to
the running state, with a tombstone, a null value, deleting a key,
because in a changelog a null means the key was removed, not set to
null. Table-to-stream emits the sequence of updates that built the
table, including the tombstones, because a downstream reconstructing
the table from the stream needs the deletions as much as the sets.
The model folds a stream into a table and emits a table's changelog,
and it treats a tombstone as a deletion in both directions rather
than a value, because a fold that stored the null would leave a
phantom key the deletion meant to remove. It refuses to fold an
update with no key, since a table is keyed and an unkeyed update
has no place in it, and reports the table size against the stream
length, because a table far smaller than the stream that built it is
a key space with heavy updates per key, the compaction ratio the
duality predicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid

TOMBSTONE = None


@dataclass
class TableStream:
    table: dict[str, int] = field(default_factory=dict)
    stream_length: int = 0

    def fold(self, key: str, value: int | None) -> None:
        if not key:
            raise Invalid("a table is keyed; an unkeyed update has no place")
        self.stream_length += 1
        if value is TOMBSTONE:
            self.table.pop(key, None)
        else:
            self.table[key] = value

    def changelog(self) -> list[tuple[str, int]]:
        # the updates that currently define the table, in key order
        return sorted(self.table.items())

    def compaction_ratio(self) -> str:
        if self.stream_length == 0:
            return "empty stream; nothing folded"
        ratio = self.stream_length / max(1, len(self.table))
        return (
            f"{self.stream_length} update(s) folded into {len(self.table)} "
            f"key(s), a {ratio:.1f}x compaction; a small table from a long "
            "stream is heavy updates per key, what the duality predicts"
        )
