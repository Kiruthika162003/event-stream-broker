"""Zombie fencing: the producer everyone thought was dead, writing again.

The worst producer failure is not a crash, it is a pause. A
transactional producer stalls, on a long garbage collection or a
network partition, and the system decides it is dead and starts a
replacement with the same transactional id. Then the paused
producer wakes, still holding an open transaction, still believing
it is the one true producer, and writes, and now two producers
share one transactional id, the split brain that duplicates and
corrupts. The fence is the transactional-id epoch. Each time a
producer initializes with a transactional id, the coordinator
bumps the epoch and records it, so the replacement gets a higher
epoch than the zombie, and every write carries its producer's
epoch. A write from the old epoch is rejected, because the epoch
has moved on and a lower epoch is by definition a producer that
has been superseded. The zombie's write bounces off the fence
with the epoch gap named, its open transaction is abortable by
the coordinator without the zombie's cooperation, and the
replacement proceeds with exclusive ownership of the id. The
subtlety the fence must handle is the zombie that wakes and tries
to commit its transaction: the commit is fenced exactly like a
write, because a committed transaction from a superseded producer
would make durable the very records the fence exists to reject,
so the epoch check guards commit and produce identically, and the
coordinator's record of the current epoch is the single source of
truth about who owns the id right now.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Fenced, Invalid


@dataclass
class TransactionalIdFencer:
    epochs: dict[str, int] = field(default_factory=dict)
    fenced_writes: int = 0
    fenced_commits: int = 0

    def initialize(self, txn_id: str) -> int:
        current = self.epochs.get(txn_id, 0)
        new_epoch = current + 1
        self.epochs[txn_id] = new_epoch
        return new_epoch

    def _check(self, txn_id: str, epoch: int) -> None:
        current = self.epochs.get(txn_id)
        if current is None:
            raise Invalid(
                f"{txn_id} was never initialized; a producer "
                "must claim its id before using it"
            )
        if epoch < current:
            raise Fenced(
                f"{txn_id} epoch {epoch} is fenced by {current}; "
                "a lower epoch is a superseded producer, the "
                "zombie that woke from a pause still believing"
            )

    def guard_write(self, txn_id: str, epoch: int) -> str:
        try:
            self._check(txn_id, epoch)
        except Fenced:
            self.fenced_writes += 1
            raise
        return f"write accepted for {txn_id} at epoch {epoch}"

    def guard_commit(self, txn_id: str, epoch: int) -> str:
        try:
            self._check(txn_id, epoch)
        except Fenced:
            self.fenced_commits += 1
            raise
        return f"commit accepted for {txn_id} at epoch {epoch}"

    def report(self) -> str:
        return (
            f"{self.fenced_writes} write(s) and "
            f"{self.fenced_commits} commit(s) fenced; the commit "
            "guard matters because a superseded producer's commit "
            "would make durable the records the fence rejects"
        )
