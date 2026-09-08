"""Sloppy quorum: when the natural replicas are down, borrow the next ones.

A strict quorum write goes to W of the partition's natural replicas
and fails if fewer than W are up, which is safe but sacrifices
availability the moment too many natural replicas are down. A
sloppy quorum keeps the write available: if some natural replicas
are down, it takes acknowledgements from the next available nodes in
the ring instead, so the write still reaches W nodes, just not all
of them the intended ones, and stores hints on the substitutes so
the writes can be handed off to the natural replicas when they
recover. This trades consistency for availability. A read from the
natural replicas right after a sloppy write might miss it, because
the write landed on substitutes the read does not consult, until
the hinted handoff moves it home, so a sloppy quorum weakens the
read-your-write guarantee a strict quorum gives during the outage.
It is the Dynamo-style choice to accept writes during a partition
rather than reject them, betting that temporary inconsistency healed
by handoff is better than unavailability. The resolver counts the
available natural replicas, borrows substitutes to reach W, and
distinguishes three outcomes: a clean write to W natural replicas, a
sloppy write to W using substitutes, and a true failure when even
substitutes cannot reach W. It refuses to claim a sloppy write
succeeded when the total available, natural plus substitute, is
below W, the real unavailability sloppiness cannot paper over. It
reports how many substitutes a write used, because a write
routinely leaning on substitutes is one whose natural replicas are
often down, an under-provisioned or unhealthy partition the sloppy
quorum is masking one write at a time."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

CLEAN = "clean"
SLOPPY = "sloppy"
FAILED = "failed"


@dataclass(frozen=True)
class SloppyQuorum:
    write_quorum: int
    natural_up: int
    substitutes_available: int

    def __post_init__(self) -> None:
        if self.write_quorum < 1:
            raise Invalid("the write quorum must be positive")
        if self.natural_up < 0 or self.substitutes_available < 0:
            raise Invalid("counts cannot be negative")

    def outcome(self) -> str:
        if self.natural_up >= self.write_quorum:
            return CLEAN
        if self.natural_up + self.substitutes_available >= self.write_quorum:
            return SLOPPY
        return FAILED

    def substitutes_used(self) -> int:
        if self.outcome() != SLOPPY:
            return 0
        return self.write_quorum - self.natural_up

    def resolve(self) -> str:
        result = self.outcome()
        if result == CLEAN:
            return f"clean write to {self.write_quorum} natural replicas"
        if result == FAILED:
            raise Invalid(
                f"only {self.natural_up + self.substitutes_available} nodes "
                f"available, below W={self.write_quorum}; sloppiness cannot "
                "paper over real unavailability, the write fails"
            )
        return (
            f"sloppy write using {self.substitutes_used()} substitute(s); "
            "available now, but a read of the natural replicas may miss it "
            "until hinted handoff moves it home"
        )
