"""Bitcask: an append-only log with a hash index, so a read is one seek.

A key-value store built on the same append-only log a broker uses
can serve a read in a single disk seek by keeping an in-memory hash
from key to the offset of that key's latest value in the log. A
write appends the key and value to the log and updates the hash to
point at the new offset; a read looks up the offset in the hash and
seeks straight to it, no scan. This is the bitcask design, and its
appeal is that writes are sequential appends, fast on any disk, and
reads are one seek, while the whole key space's locations fit in
memory as long as the keys do. The catch is that the log keeps every
version ever written, since it only appends, so a key updated a
thousand times has a thousand entries in the log and only the
latest is live, the rest dead weight the hash no longer points at.
Compaction reclaims that: it copies the live value of each key,
the one the hash points at, into a new log and drops the dead
versions, shrinking the log to the live set. A delete writes a
tombstone, a marker that removes the key from the hash, and
compaction drops both the tombstone and the values it shadowed. The
store appends on write, looks up on read, tombstones on delete, and
compacts to the live set, and it refuses a read of a key not in the
hash, a genuine miss the caller handles. It reports the dead-entry
ratio, the log entries no longer live, because a ratio climbing
toward all-dead is a store overdue for compaction, its log far
larger than the data it holds, the append-only cost compaction
exists to pay down.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Missing

_TOMBSTONE = object()


@dataclass
class Bitcask:
    log: list[tuple[str, object]] = field(default_factory=list)
    index: dict[str, int] = field(default_factory=dict)

    def put(self, key: str, value: str) -> int:
        offset = len(self.log)
        self.log.append((key, value))
        self.index[key] = offset
        return offset

    def get(self, key: str) -> str:
        if key not in self.index:
            raise Missing(f"no live value for key '{key}'")
        _key, value = self.log[self.index[key]]
        if value is _TOMBSTONE:
            raise Missing(f"key '{key}' was deleted")
        return value  # type: ignore[return-value]

    def delete(self, key: str) -> None:
        if key not in self.index:
            raise Missing(f"cannot delete absent key '{key}'")
        self.log.append((key, _TOMBSTONE))
        del self.index[key]

    def compact(self) -> str:
        before = len(self.log)
        new_log: list[tuple[str, object]] = []
        new_index: dict[str, int] = {}
        for key, offset in self.index.items():
            new_index[key] = len(new_log)
            new_log.append(self.log[offset])
        self.log = new_log
        self.index = new_index
        return f"compacted {before} entries to {len(self.log)} live"

    def dead_ratio(self) -> str:
        total = len(self.log)
        if total == 0:
            return "empty log"
        live = len(self.index)
        dead = total - live
        pct = dead / total * 100
        return (
            f"{dead}/{total} log entries dead ({pct:.0f}%); a ratio climbing "
            "toward all-dead is a store overdue for compaction, its log far "
            "larger than the data"
        )
