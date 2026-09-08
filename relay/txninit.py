"""Transactional init: the handshake that must finish before the first write.

A transactional producer cannot just start producing; it must
first complete an initialization handshake that does two things
in order, and skipping either is a correctness bug. First it
claims its transactional id and receives an epoch, which fences
any older instance of the same id, the zombie from a previous
run. Second, and this is the step everyone forgets, the
coordinator recovers any transaction the previous instance left
open: if the old producer died mid-transaction, that transaction
is still pending, holding records invisible to read-committed
consumers, and the new producer cannot begin its own work until
that dangling transaction is resolved, aborted, because a new
transaction started while an old one dangles would interleave two
transactions under one id. So init is claim-epoch-then-recover,
and the recovery is not optional: a producer that claimed its
epoch but skipped recovery could begin producing while its
predecessor's transaction still holds the log, and the two would
tangle. The sequencer enforces the order, refusing a begin before
init completes and refusing init to skip the recovery of a
dangling transaction, and it reports what recovery found, a clean
slate or an aborted straggler, because a producer that keeps
finding dangling transactions on init is a producer that keeps
dying mid-transaction, a crash loop worth investigating that a
silent recovery would hide.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

UNINITIALIZED = "uninitialized"
EPOCH_CLAIMED = "epoch-claimed"
READY = "ready"


@dataclass
class TransactionalInit:
    txn_id: str
    state: str = UNINITIALIZED
    epoch: int = 0
    recovered_dangling: int = 0

    def claim_epoch(self, new_epoch: int) -> str:
        if new_epoch <= self.epoch and self.epoch != 0:
            raise Invalid(
                "the new epoch must exceed the old; a lower epoch "
                "would not fence the zombie it exists to fence"
            )
        self.epoch = new_epoch
        self.state = EPOCH_CLAIMED
        return f"{self.txn_id} claimed epoch {new_epoch}"

    def recover(self, dangling_open: bool) -> str:
        if self.state != EPOCH_CLAIMED:
            raise Invalid(
                "recover runs after claiming the epoch, not "
                "before; the order is claim-then-recover"
            )
        self.state = READY
        if dangling_open:
            self.recovered_dangling += 1
            return (
                f"{self.txn_id} recovered a dangling transaction "
                "from a dead predecessor, aborted it; a new one "
                "started over it would have tangled two under one "
                "id"
            )
        return f"{self.txn_id} recovered a clean slate, ready"

    def begin_transaction(self) -> str:
        if self.state != READY:
            raise Invalid(
                f"{self.txn_id} is {self.state}, not ready; a "
                "begin before init completes could produce while "
                "a predecessor's transaction still holds the log"
            )
        return f"{self.txn_id} may begin a transaction"
