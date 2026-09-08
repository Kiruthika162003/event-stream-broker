"""LSM tree: writes hit memory, flush to sorted runs, reads check newest first.

A log-structured merge tree turns random writes into sequential
ones, the same instinct as the broker's append-only log applied to
a key-value store. Writes go to an in-memory memtable, a sorted
structure that absorbs them cheaply, and when it fills it is flushed
to disk as an immutable sorted run, so the disk only ever sees
sequential writes of whole runs, never random updates in place.
Reads are the cost side: a key may be in the memtable or any run,
and a newer write shadows an older, so a read checks the memtable
first, then the runs newest to oldest, returning the first value it
finds, which is the latest. Without help, that means a read can
touch every run, so each run carries a bloom filter that says
definitely-not for keys it lacks, letting a read skip the runs that
cannot hold the key and touch only the few that might. Over time
the runs accumulate and reads slow, so compaction merges runs
together, dropping shadowed old values and keeping the latest per
key, trading write amplification, rewriting data during compaction,
for bounded read cost. This is the LSM tradeoff: fast sequential
writes and compaction work in exchange for reads that fan out
across runs, the opposite balance from a b-tree's in-place updates.
The tree writes to the memtable, flushes it to a run when full,
reads newest-first across the memtable and runs, and compacts runs
into one. It refuses to flush an empty memtable, a no-op that would
add an empty run to scan, and reports the run count, because a read
touching many runs is an LSM behind on compaction, the read-fan-out
cost of deferring the merge."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid, Missing

_TOMBSTONE = object()


@dataclass
class LSMTree:
    memtable_limit: int
    memtable: dict[str, object] = field(default_factory=dict)
    runs: list[dict[str, object]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.memtable_limit < 1:
            raise Invalid("the memtable limit must be positive")

    def put(self, key: str, value: str) -> None:
        self.memtable[key] = value
        if len(self.memtable) >= self.memtable_limit:
            self.flush()

    def delete(self, key: str) -> None:
        self.memtable[key] = _TOMBSTONE

    def flush(self) -> str:
        if not self.memtable:
            raise Invalid("refusing to flush an empty memtable; it adds an empty run to scan")
        self.runs.append(dict(self.memtable))
        self.memtable = {}
        return f"flushed a run; {len(self.runs)} run(s) on disk"

    def get(self, key: str) -> str:
        if key in self.memtable:
            value = self.memtable[key]
        else:
            value = None
            for run in reversed(self.runs):
                if key in run:
                    value = run[key]
                    break
        if value is None or value is _TOMBSTONE:
            raise Missing(f"no live value for key '{key}'")
        return value  # type: ignore[return-value]

    def compact(self) -> str:
        merged: dict[str, object] = {}
        for run in self.runs:  # oldest to newest, newer overwrites
            merged.update(run)
        merged = {k: v for k, v in merged.items() if v is not _TOMBSTONE}
        before = len(self.runs)
        self.runs = [merged] if merged else []
        return f"compacted {before} run(s) into {len(self.runs)}"

    def read_fanout(self) -> str:
        return (
            f"a read may check the memtable and {len(self.runs)} run(s); many "
            "runs is an LSM behind on compaction, the read-fan-out cost of "
            "deferring the merge"
        )
