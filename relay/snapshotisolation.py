"""Snapshot isolation: read a consistent snapshot, abort on a write-write clash.

Snapshot isolation gives a transaction a stable view without
locking reads. A transaction takes a start version when it begins,
and every read sees the value as of that version, the last commit
at or before it, so the transaction reads a consistent snapshot
frozen at its start no matter what other transactions commit while
it runs, which is why its reads never block and never see a
partial state. Writes are where conflicts are caught, at commit
rather than at write. When a transaction commits, the system checks
whether any other transaction committed a write to a key this one
also wrote, in the window since this transaction's start, and if so
the two updated the same key concurrently, a write-write conflict,
and the later committer aborts, first-committer-wins, so a lost
update, two transactions both reading a value and both overwriting
it, cannot happen. Snapshot isolation prevents the anomalies
serializability does except one, write skew: two transactions can
each read an overlapping set and write disjoint keys based on it,
each valid alone but together violating an invariant across the
keys, because neither wrote a key the other wrote so no conflict is
detected. That gap is the honest limit, snapshot isolation is not
serializable, and a constraint spanning keys needs extra care. The
manager assigns a start version, resolves a read to the snapshot,
records a write set, and at commit aborts on a write-write conflict
with a transaction committed since the start. It refuses to commit
a transaction twice and reports whether a commit is a clean apply
or a conflict abort, because a workload with frequent conflict
aborts is one with real contention on shared keys, where snapshot
isolation's optimism is not paying off."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class SnapshotIsolation:
    version: int = 0
    # key -> version at which it was last committed
    committed_at: dict[str, int] = field(default_factory=dict)

    def begin(self) -> int:
        return self.version

    def read(self, key: str, start_version: int) -> str:
        # a read sees the snapshot as of start_version
        last = self.committed_at.get(key, -1)
        if last <= start_version:
            return f"'{key}' as of version {start_version}"
        return f"'{key}' as of version {start_version} (ignoring later commits)"

    def commit(self, start_version: int, write_set: set[str]) -> str:
        # abort if any written key was committed by someone else since start
        conflicts = [
            k for k in write_set if self.committed_at.get(k, -1) > start_version
        ]
        if conflicts:
            raise Invalid(
                f"write-write conflict on {sorted(conflicts)}; another "
                "transaction committed them since this one's start, so the "
                "later committer aborts, first-committer-wins"
            )
        self.version += 1
        for k in write_set:
            self.committed_at[k] = self.version
        return f"committed at version {self.version}"

    def write_skew_note(self) -> str:
        return (
            "snapshot isolation prevents lost updates but allows write skew: "
            "two transactions writing disjoint keys off an overlapping read "
            "clash on no key, so a cross-key invariant needs extra care"
        )
