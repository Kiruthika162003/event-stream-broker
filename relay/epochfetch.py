"""Epoch fetch: a follower proves it did not diverge before it trusts a fetch.

When leadership changes, the new leader may have a different log
past some offset than a follower does, because the old leader
accepted writes the new leader never saw, and if the follower
simply continues fetching from its current offset it appends the
new leader's records after its own divergent ones, silently
creating a log that never existed on any leader. The leader epoch
prevents this. The follower's log records, for each offset range,
which leader epoch produced it, and before fetching the follower
sends its latest epoch and offset; the leader replies with the
offset at which that epoch ended on the leader's log. If the
follower's log extends past that point, those records are from a
divergent history and must be truncated, so the follower discards
them and resumes fetching from the divergence point, its log now
a strict prefix of the leader's. This truncation is the correct
loss: the discarded records were never committed, never
acknowledged to a producer, because if they had been committed
the new leader would have had them, so truncating them loses
nothing the system promised. The validator computes the
truncation point from the epoch handshake and refuses to let a
follower append new records while its log still diverges, because
appending onto a divergent log is the exact corruption the epoch
check exists to prevent, and it reports how many records were
truncated, because a large truncation after a leadership change
means the old leader accepted many unreplicated writes, a sign
its replication was lagging before it failed, worth investigating
even though no data promised to anyone was lost.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class EpochBoundary:
    epoch: int
    end_offset: int


def truncation_point(
    follower_epoch: int,
    follower_end: int,
    leader_epoch_end: int,
) -> tuple[int, str]:
    if follower_end <= leader_epoch_end:
        return follower_end, (
            "no truncation: the follower's log is already a prefix "
            "of the leader's, nothing diverged"
        )
    truncated = follower_end - leader_epoch_end
    return leader_epoch_end, (
        f"truncate {truncated} record(s) to offset "
        f"{leader_epoch_end}: divergent history from epoch "
        f"{follower_epoch}, never committed so nothing promised is "
        "lost, but a large truncation means the old leader was "
        "lagging before it failed"
    )


@dataclass
class DivergenceGuard:
    diverged_past: int | None = None

    def require_truncation(
        self, follower_end: int, leader_epoch_end: int
    ) -> None:
        if follower_end > leader_epoch_end:
            self.diverged_past = leader_epoch_end
            raise Invalid(
                "cannot append while the log diverges past "
                f"{leader_epoch_end}; appending onto a divergent "
                "log is the exact corruption the epoch check "
                "prevents, truncate first"
            )

    def resolve(self, truncated_to: int) -> str:
        if self.diverged_past is None:
            return "no divergence to resolve"
        if truncated_to != self.diverged_past:
            raise Invalid(
                f"truncated to {truncated_to} but divergence is "
                f"at {self.diverged_past}; the log is still not a "
                "prefix"
            )
        self.diverged_past = None
        return (
            "divergence resolved: the log is now a strict prefix "
            "of the leader's and may append again"
        )
