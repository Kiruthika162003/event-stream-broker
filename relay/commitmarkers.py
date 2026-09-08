"""Commit markers: a transaction is committed only when every partition knows.

Committing a transaction is not a single write, because the
transaction wrote to several partitions and each of them must be
told the transaction committed so its records become visible to
read-committed consumers. The coordinator writes a commit marker, a
control record, to every partition the transaction touched, and the
transaction is committed only when all of those markers are
durable, so commit latency scales with the number of partitions the
transaction spanned: a transaction across two partitions commits
fast while one across fifty writes fifty markers and commits
slower. This is a real cost of spreading a transaction wide, and a
reason to keep a transaction's partition set no larger than it
needs to be. The marker write is where a coordinator crash is most
dangerous, because a crash after some markers are written but not
all leaves the transaction half-committed on the log, visible on
the partitions that got their marker and not on those that did not,
so recovery must finish the job: a new coordinator re-drives the
remaining markers to completion, using the transaction's recorded
partition set to know which still need one. The tracker records the
partitions a transaction wrote to, writes markers, and reports the
transaction committed only once every partition has its marker, and
it refuses to declare a transaction committed with markers still
outstanding, the half-committed state that would show a consumer a
partial transaction. It refuses to write a marker to a partition
the transaction never wrote to, a spurious marker that would
confuse that partition's read-committed logic. The report states
how many markers remain, because a commit stuck with markers
outstanding is a coordinator that crashed mid-commit and whose
recovery has not yet re-driven the rest.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class CommitMarkers:
    partitions: set[str]
    written: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not self.partitions:
            raise Invalid("a transaction with no partitions has nothing to commit")

    def write_marker(self, partition: str) -> str:
        if partition not in self.partitions:
            raise Invalid(
                f"partition '{partition}' was not written by this "
                "transaction; a spurious marker confuses its read-committed "
                "logic"
            )
        self.written.add(partition)
        return f"marker written to '{partition}' ({len(self.written)}/{len(self.partitions)})"

    def outstanding(self) -> set[str]:
        return self.partitions - self.written

    def is_committed(self) -> bool:
        return not self.outstanding()

    def declare_committed(self) -> str:
        if not self.is_committed():
            raise Invalid(
                f"cannot declare committed with {len(self.outstanding())} "
                "marker(s) outstanding; that half-committed state would show "
                "a consumer a partial transaction"
            )
        return f"committed across all {len(self.partitions)} partition(s)"

    def recover(self) -> str:
        remaining = self.outstanding()
        if not remaining:
            return "all markers written; nothing to recover"
        return (
            f"re-driving {len(remaining)} outstanding marker(s) "
            f"{sorted(remaining)}; a coordinator crashed mid-commit"
        )
