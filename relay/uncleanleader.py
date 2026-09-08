"""Unclean leader election: trade durability for availability when the ISR empties.

A partition stays available as long as one in-sync replica survives to
become leader. When the last in-sync replica fails, there is a choice
with no free option. Wait for an in-sync replica to come back, and the
partition is unavailable until one does, no produce and no consume,
but no committed record is lost, because the next leader will have had
every committed record by the definition of in-sync. Or elect a
replica that was out of sync, an unclean election, and the partition
is available again immediately, but that replica is behind, missing
the records committed after it fell out of sync, and those records are
lost, silently, because the new leader's log end becomes the truth and
the missing tail is simply gone. This is a genuine durability-versus-
availability decision, not a bug to fix, and the broker exposes it as
a per-topic switch rather than deciding for the operator. The default
is to refuse the unclean election, favoring durability, because a
silent loss of acknowledged records is worse for most topics than a
pause. A topic that values availability over durability, a metrics
firehose where a gap matters less than a stall, can turn it on. The
elector tracks the in-sync set and the log end offsets, chooses the
in-sync replica with the highest log end when the ISR is non-empty,
refuses any election when the ISR is empty and unclean election is
off, and when it is on picks the out-of-sync replica with the highest
log end and reports the loss window, the number of records between
the old committed offset and the new leader's log end, because an
unclean election that loses records must say how many it lost, not
paper over it."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class UncleanLeaderElection:
    committed_offset: int
    allow_unclean: bool = False
    # replica id -> log end offset
    log_ends: dict[str, int] = field(default_factory=dict)
    in_sync: set[str] = field(default_factory=set)

    def set_replica(self, replica: str, log_end: int, *, in_sync: bool) -> None:
        self.log_ends[replica] = log_end
        if in_sync:
            self.in_sync.add(replica)
        else:
            self.in_sync.discard(replica)

    def elect(self) -> str:
        if self.in_sync:
            # a clean election: the in-sync replica with the highest log end
            leader = max(self.in_sync, key=lambda r: self.log_ends.get(r, -1))
            return f"clean election of '{leader}'; no committed record is lost"

        if not self.allow_unclean:
            raise Invalid(
                "the in-sync set is empty and unclean election is off; the "
                "partition stays unavailable until an in-sync replica returns, "
                "favoring durability over availability"
            )

        if not self.log_ends:
            raise Invalid("no replica is available to elect, not even an unclean one")
        leader = max(self.log_ends, key=lambda r: self.log_ends[r])
        loss = max(0, self.committed_offset - self.log_ends[leader])
        return (
            f"unclean election of '{leader}'; {loss} committed record(s) lost, "
            "the tail past this replica's log end is gone, availability chosen "
            "over durability"
        )

    def loss_window(self, replica: str) -> int:
        if replica not in self.log_ends:
            raise Invalid(f"'{replica}' has no known log end")
        return max(0, self.committed_offset - self.log_ends[replica])

    def note(self) -> str:
        mode = "on" if self.allow_unclean else "off"
        return (
            f"{len(self.in_sync)} in-sync of {len(self.log_ends)} replica(s), "
            f"unclean election {mode}; with an empty ISR this switch is the "
            "durability-versus-availability decision, not a bug to fix"
        )
