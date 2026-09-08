"""Describe transactions: the state each one is in, and the ones stuck between.

A transaction moves through states, and listing them is how an
operator sees the health of the transactional workload: a
transaction that is ongoing is a producer actively writing, one
that is completing is mid-commit or mid-abort, and one that has
completed is done. The states that matter for an incident are the
in-between ones. A transaction in prepare-commit or prepare-abort
has decided its outcome but not finished writing the markers to
every partition, and if the coordinator crashes there, the
transaction is stuck in prepare until a new coordinator recovers
it and completes the markers. A transaction stuck in a prepare
state holds its partitions' last stable offsets down the same way
an ongoing one does, so a long-lived prepare is as much a problem
as a hung ongoing transaction, and describe-transactions surfaces
both by state and duration. The tool lists transactions filtered by
state, so an operator can ask for just the ongoing ones or just the
stuck-preparing ones rather than reading the whole set, and it
flags a transaction whose duration in a non-terminal state exceeds
the timeout as one the coordinator should force to completion. It
refuses to report a transaction in the dead state as active,
because a dead transactional id has been expired and listing it as
live would point an operator at something already gone, and it
distinguishes an empty transaction, a transactional id registered
with no transaction in progress, from an ongoing one, because the
empty one pins nothing while the ongoing one pins its partitions.
The report counts transactions by state and names the longest-
running non-terminal one, because that is the transaction most
likely to be stuck and the first to investigate when the LSO lags.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid

EMPTY = "Empty"
ONGOING = "Ongoing"
PREPARE_COMMIT = "PrepareCommit"
PREPARE_ABORT = "PrepareAbort"
COMPLETE = "Complete"
DEAD = "Dead"
_NON_TERMINAL = (ONGOING, PREPARE_COMMIT, PREPARE_ABORT)


@dataclass(frozen=True)
class TxnRecord:
    txn_id: str
    state: str
    duration_ticks: int
    partitions: int


@dataclass
class TransactionDirectory:
    transactions: list[TxnRecord] = field(default_factory=list)

    def in_state(self, state: str) -> list[TxnRecord]:
        return [t for t in self.transactions if t.state == state]

    def active(self) -> list[TxnRecord]:
        return [t for t in self.transactions if t.state != DEAD]

    def stuck(self, timeout: int) -> list[str]:
        return [
            t.txn_id
            for t in self.transactions
            if t.state in _NON_TERMINAL and t.duration_ticks > timeout
        ]

    def longest_non_terminal(self) -> TxnRecord | None:
        candidates = [t for t in self.transactions if t.state in _NON_TERMINAL]
        if not candidates:
            return None
        return max(candidates, key=lambda t: t.duration_ticks)

    def report(self, timeout: int) -> str:
        if any(t.state == DEAD for t in self.transactions):
            live = self.active()
        else:
            live = self.transactions
        counts: dict[str, int] = {}
        for t in live:
            counts[t.state] = counts.get(t.state, 0) + 1
        longest = self.longest_non_terminal()
        head = ", ".join(f"{s}: {n}" for s, n in sorted(counts.items()))
        if longest is None:
            return f"{head}; no non-terminal transactions, nothing pinning an LSO"
        flag = ""
        if longest.txn_id in self.stuck(timeout):
            flag = " (past timeout, force to complete)"
        return (
            f"{head}; longest non-terminal '{longest.txn_id}' in "
            f"{longest.state} for {longest.duration_ticks} tick(s){flag}"
        )

    def assert_not_dead(self, txn_id: str) -> None:
        for t in self.transactions:
            if t.txn_id == txn_id and t.state == DEAD:
                raise Invalid(
                    f"transaction '{txn_id}' is dead; its id was expired "
                    "and listing it as live points at something gone"
                )
