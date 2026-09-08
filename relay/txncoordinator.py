"""The transaction coordinator: one authority per producer, fencing zombies.

Transactions need a coordinator, a broker that owns the state of
every in-flight transaction for a set of producers and drives
the two-phase commit that makes a multi-partition write atomic.
Its central job is fencing: a transactional producer registers a
stable transactional-id and receives a producer-epoch, and the
coordinator bumps that epoch every time a new instance registers
with the same id. The bump is the fence: any write or commit
bearing an epoch below the current one is a zombie, a previous
producer instance that hung and came back, and rejecting it is
what prevents a resurrected producer from committing a
transaction its replacement already aborted. The coordinator
also enforces that a producer has exactly one open transaction
at a time, because a producer that could open a second before
committing the first would blur which records belong to which
outcome. When a producer's transaction times out, the
coordinator aborts it and bumps the epoch, so the next attempt
by even the same producer starts clean and the timed-out
records are never resurrected.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Fenced, Invalid


@dataclass
class ProducerTxnState:
    transactional_id: str
    epoch: int
    open_txn: bool = False


@dataclass
class TransactionCoordinator:
    producers: dict[str, ProducerTxnState] = field(
        default_factory=dict
    )
    zombies_fenced: int = 0

    def register(self, transactional_id: str) -> int:
        held = self.producers.get(transactional_id)
        if held is None:
            self.producers[transactional_id] = ProducerTxnState(
                transactional_id=transactional_id, epoch=0
            )
            return 0
        held.epoch += 1
        held.open_txn = False
        return held.epoch

    def _live(
        self, transactional_id: str, epoch: int
    ) -> ProducerTxnState:
        state = self.producers.get(transactional_id)
        if state is None:
            raise Invalid(
                f"{transactional_id} is not registered"
            )
        if epoch < state.epoch:
            self.zombies_fenced += 1
            raise Fenced(
                f"{transactional_id} epoch {epoch} is behind "
                f"{state.epoch}; a resurrected producer cannot "
                "commit a transaction its replacement handled"
            )
        return state

    def begin(self, transactional_id: str, epoch: int) -> str:
        state = self._live(transactional_id, epoch)
        if state.open_txn:
            raise Invalid(
                f"{transactional_id} already has an open "
                "transaction; a second would blur which records "
                "belong to which outcome"
            )
        state.open_txn = True
        return f"{transactional_id} began a transaction at epoch {epoch}"

    def complete(
        self, transactional_id: str, epoch: int, commit: bool
    ) -> str:
        state = self._live(transactional_id, epoch)
        if not state.open_txn:
            raise Invalid(
                f"{transactional_id} has no open transaction to "
                f"{'commit' if commit else 'abort'}"
            )
        state.open_txn = False
        verb = "committed" if commit else "aborted"
        return f"{transactional_id} {verb} at epoch {epoch}"

    def timeout_abort(self, transactional_id: str) -> str:
        state = self.producers.get(transactional_id)
        if state is None or not state.open_txn:
            raise Invalid("no open transaction to time out")
        state.open_txn = False
        state.epoch += 1
        return (
            f"{transactional_id} timed out, aborted, epoch "
            f"bumped to {state.epoch}; the next attempt starts "
            "clean and the timed-out records never resurrect"
        )
