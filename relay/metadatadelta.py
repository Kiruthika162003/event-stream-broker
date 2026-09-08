"""Metadata delta: send only what changed, and detect the gap that breaks it.

The controller keeps every broker's view of the cluster current by
publishing metadata changes, and sending the entire metadata on
every change would be wasteful when a single leader moved, so it
sends deltas: the initial state as a full image, then a stream of
incremental updates each carrying only what changed since the last.
A broker applies deltas in order to keep its view current without
re-receiving the parts that did not change. The correctness of this
rests entirely on ordering and completeness: each delta is numbered,
and a broker must apply them in unbroken sequence, because a delta
describes a change relative to the state the previous delta left, so
applying delta five without delta four would build on a state that
never existed. A broker that receives a delta whose number is not
exactly one past its last applied has missed one, and the only safe
recovery is a full resync, re-fetching the complete image, because
the missed delta's changes cannot be reconstructed from the deltas
around it. The applier refuses a delta that skips a number, signaling
the resync rather than applying it onto a state with a hole, and it
refuses a delta older than the last applied, a duplicate or reorder
that would undo a change already incorporated. A duplicate of the
exact last-applied delta is a harmless no-op rather than an error,
because a controller resending the last delta after an
acknowledgement it did not hear is expected, not a fault. The report
states the applied sequence and whether the view is whole, because a
broker acting on a metadata view with a gap routes on stale
leadership, the split-brain the ordering exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class MetadataApplier:
    applied_seq: int = -1
    needs_resync: bool = False

    def full_image(self, seq: int) -> str:
        self.applied_seq = seq
        self.needs_resync = False
        return f"full image applied at sequence {seq}"

    def apply_delta(self, seq: int) -> str:
        if seq == self.applied_seq:
            return f"delta {seq} is a duplicate of the last applied; no-op"
        if seq < self.applied_seq:
            raise Invalid(
                f"delta {seq} is older than the last applied "
                f"{self.applied_seq}; a reorder that would undo a change "
                "already incorporated"
            )
        if seq != self.applied_seq + 1:
            self.needs_resync = True
            raise Invalid(
                f"delta {seq} skips past {self.applied_seq + 1}; a delta "
                "was missed and its change cannot be reconstructed, so a "
                "full resync is required"
            )
        self.applied_seq = seq
        return f"delta {seq} applied"

    def view_status(self) -> str:
        if self.needs_resync:
            return (
                f"view has a gap after sequence {self.applied_seq}; a "
                "resync is pending, and acting now routes on stale "
                "leadership, the split-brain ordering prevents"
            )
        return f"view whole through sequence {self.applied_seq}"
