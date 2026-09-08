"""Leader election: the new leader must have the old leader's promises.

When a partition leader dies, a follower is promoted, and the
one rule that cannot bend is that the new leader must hold every
committed record the old leader served, because a leader missing
a committed record would let the log lose data that consumers
already read. So the election is not a popularity contest; it is
a filter: only replicas whose log end is at least the last
committed offset are eligible, and among the eligible the one
with the longest log wins to minimize truncation elsewhere. The
leader epoch is the fence: every leadership term gets a
strictly higher epoch, and any message from a prior epoch is
rejected, because a deposed leader that wakes from a pause still
believing it leads is the split-brain that duplicates and
diverges. Unclean election is the explicit escape hatch: when no
in-sync replica survives, the operator may promote an out-of-
sync one, trading committed data for availability, and the
broker records that this was a choice with a name, not a
silent default, because losing acknowledged data must never
happen by accident.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Fenced, Invalid


@dataclass(frozen=True)
class Candidate:
    name: str
    log_end_offset: int
    in_sync: bool


@dataclass
class ElectionResult:
    leader: str
    epoch: int
    truncation_note: str
    unclean: bool


@dataclass
class PartitionElector:
    epoch: int = 0
    committed_offset: int = 0

    def elect(
        self,
        candidates: list[Candidate],
        allow_unclean: bool = False,
    ) -> ElectionResult:
        if not candidates:
            raise Invalid("no candidates; the partition is dark")
        eligible = [
            c
            for c in candidates
            if c.in_sync
            and c.log_end_offset >= self.committed_offset
        ]
        unclean = False
        if not eligible:
            if not allow_unclean:
                raise Invalid(
                    "no in-sync replica holds the committed "
                    "offset; promoting an out-of-sync replica "
                    "loses acknowledged data and must be an "
                    "explicit unclean election, never a default"
                )
            eligible = sorted(
                candidates,
                key=lambda c: (-c.log_end_offset, c.name),
            )
            unclean = True
        winner = sorted(
            eligible, key=lambda c: (-c.log_end_offset, c.name)
        )[0]
        self.epoch += 1
        max_end = max(c.log_end_offset for c in candidates)
        note = (
            f"followers truncate to {winner.log_end_offset}; "
            f"{max_end - winner.log_end_offset} record(s) "
            "beyond the new leader are discarded"
        )
        return ElectionResult(
            leader=winner.name,
            epoch=self.epoch,
            truncation_note=note,
            unclean=unclean,
        )

    def accept_from(self, epoch: int) -> None:
        if epoch < self.epoch:
            raise Fenced(
                f"message from epoch {epoch} rejected; the "
                f"current term is {self.epoch}, and a deposed "
                "leader waking from a pause is the split-brain "
                "that diverges"
            )
