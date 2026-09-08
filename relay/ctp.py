"""Consume-transform-produce: the offset commit rides inside the transaction.

The most common stream-processing shape reads from one topic,
transforms, and writes to another, and doing it exactly-once
hinges on one insight that trips up every first implementation.
The output records and the input offset commit must be in the
same transaction. If the process commits the input offset
separately from producing the output, a crash between them either
reprocesses input whose output already shipped, duplicating, or
skips input whose output never shipped, losing. Binding both into
one atomic transaction closes the gap: either the output records
and the consumed offset both commit, or neither does, so a crash
replays exactly the input whose output did not survive. The
coordinator that owns the transaction therefore accepts offset
commits as transactional operations alongside produces, and a
read-committed downstream sees the outputs only when the
transaction commits, which is also when the input offset
advances. The loop refuses to commit an offset outside a
transaction when the processor declared exactly-once, because a
bare offset commit in an exactly-once processor is the exact bug
the transaction exists to prevent, silently reintroduced by a
convenience method.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class ProcessingTransaction:
    exactly_once: bool
    open: bool = False
    produced: list[tuple[str, int]] = field(default_factory=list)
    offset_commit: tuple[str, int, int] | None = None

    def begin(self) -> None:
        if self.open:
            raise Invalid("a transaction is already open")
        self.open = True
        self.produced = []
        self.offset_commit = None

    def produce(self, topic: str, offset: int) -> None:
        if not self.open:
            raise Invalid("produce inside a transaction")
        self.produced.append((topic, offset))

    def commit_offset(
        self, group: str, partition: int, offset: int
    ) -> None:
        if not self.open:
            raise Invalid("the offset commit rides the transaction")
        self.offset_commit = (group, partition, offset)

    def commit(self) -> str:
        if not self.open:
            raise Invalid("no open transaction to commit")
        if self.exactly_once and self.offset_commit is None:
            raise Invalid(
                "exactly-once requires the input offset to "
                "commit inside the transaction; committing "
                "output without the offset duplicates on a crash"
            )
        self.open = False
        return (
            f"committed {len(self.produced)} output(s) and the "
            "input offset atomically; a crash now replays only "
            "unshipped input"
        )

    def abort(self) -> str:
        if not self.open:
            raise Invalid("no open transaction to abort")
        self.open = False
        return (
            f"aborted: {len(self.produced)} output(s) and the "
            "offset both roll back, so neither half survives"
        )


def bare_commit_check(exactly_once: bool) -> None:
    if exactly_once:
        raise Invalid(
            "a bare offset commit in an exactly-once processor "
            "is the exact bug the transaction prevents, silently "
            "reintroduced by a convenience method"
        )
