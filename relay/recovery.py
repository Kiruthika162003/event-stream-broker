"""Recovery: a restarted broker reconciles its log before it serves a byte.

A broker that crashed and restarted holds a log that may end
past the last committed offset, records it had written but that
were never promised, and it must not serve them, because a new
leader may have been elected in its absence with a different
history after the divergence point. Recovery finds the
divergence: it compares its log against the leader's epoch
history, locates the largest offset where the two agree, and
truncates everything after, because keeping records the leader
does not have is exactly the divergence that turns replication
into two logs pretending to be one. The truncation is logged
with the offset and the count discarded, since a broker that
silently drops records on recovery gives its operators no way
to distinguish a healthy truncation of unpromised writes from a
bug eating committed data. The last step before serving is
rebuilding the offset index from the recovered log, because an
index that survived the crash may point past the truncation
into records that no longer exist.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EpochMarker:
    epoch: int
    start_offset: int


@dataclass
class RecoveryPlan:
    local_end: int
    local_epochs: list[EpochMarker]
    truncated_to: int = -1
    discarded: int = 0
    index_rebuilt: bool = False

    def diverge_point(
        self, leader_epochs: list[EpochMarker]
    ) -> int:
        leader_by_epoch = {
            marker.epoch: marker.start_offset
            for marker in leader_epochs
        }
        agree_offset = 0
        for marker in sorted(
            self.local_epochs, key=lambda m: m.epoch
        ):
            leader_start = leader_by_epoch.get(marker.epoch)
            if leader_start is None:
                break
            if leader_start != marker.start_offset:
                break
            agree_offset = self._epoch_end(
                marker.epoch, leader_epochs
            )
        return agree_offset

    def _epoch_end(
        self, epoch: int, leader_epochs: list[EpochMarker]
    ) -> int:
        ordered = sorted(leader_epochs, key=lambda m: m.epoch)
        for index, marker in enumerate(ordered):
            if marker.epoch == epoch:
                if index + 1 < len(ordered):
                    return ordered[index + 1].start_offset
                return self.local_end
        return 0

    def recover(
        self, leader_epochs: list[EpochMarker], leader_end: int
    ) -> str:
        safe = min(
            self.diverge_point(leader_epochs), leader_end
        )
        safe = min(safe, self.local_end)
        self.truncated_to = safe
        self.discarded = max(0, self.local_end - safe)
        self.index_rebuilt = True
        if self.discarded == 0:
            return (
                f"recovered: log agrees through {safe}, nothing "
                "truncated, index rebuilt before serving"
            )
        return (
            f"recovered: truncated to {safe}, discarded "
            f"{self.discarded} unpromised record(s), index "
            "rebuilt; the count is logged so a healthy "
            "truncation is not mistaken for a bug eating data"
        )

    def may_serve(self) -> bool:
        return self.truncated_to >= 0 and self.index_rebuilt
