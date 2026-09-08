"""Rack spread: a partition survives a rack loss only if it spans enough racks.

Placement puts replicas in different racks when it can, but the
guarantee an operator actually needs is quantitative: how many
racks can fail before a partition loses its majority, or all its
replicas. That depends on how the replicas are distributed across
racks, not just that they are spread. A partition with three
replicas in three racks survives one rack failure with a majority
intact; the same three replicas with two in one rack and one in
another lose their majority when the two-replica rack fails, even
though they are technically in two racks. The analyzer computes,
from a partition's rack distribution, the minimum number of rack
failures that would drop it below its in-sync minimum, which is
the real fault tolerance, and it names the concentration that
limits it: a partition is only as rack-fault-tolerant as its most
loaded rack, because losing that rack removes the most replicas at
once. The analyzer flags the specific anti-pattern of a majority
of replicas in one rack, which looks redundant, three replicas,
but tolerates zero rack failures for a majority quorum, because
the one rack holds the majority and its loss takes the quorum with
it. It reports the tolerance as a number of survivable rack
failures, because that is the promise an operator can reason about
during a datacenter event, and a spread that reads as redundant
while surviving zero rack failures is exactly the false comfort
the analyzer exists to expose before the event, not during it.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class RackDistribution:
    replicas_per_rack: dict[str, int]
    min_in_sync: int

    def __post_init__(self) -> None:
        if not self.replicas_per_rack:
            raise Invalid("a partition has replicas somewhere")
        if self.min_in_sync < 1:
            raise Invalid("min in-sync must be positive")

    def total_replicas(self) -> int:
        return sum(self.replicas_per_rack.values())

    def survivable_rack_failures(self) -> int:
        # remove racks largest-first until we drop below min_in_sync
        sizes = sorted(
            self.replicas_per_rack.values(), reverse=True
        )
        remaining = self.total_replicas()
        failures = 0
        for size in sizes:
            if remaining - size < self.min_in_sync:
                break
            remaining -= size
            failures += 1
        return failures

    def report(self) -> str:
        tolerance = self.survivable_rack_failures()
        heaviest = max(
            self.replicas_per_rack,
            key=lambda r: self.replicas_per_rack[r],
        )
        load = self.replicas_per_rack[heaviest]
        note = ""
        if tolerance == 0:
            note = (
                "; looks redundant but survives zero rack "
                "failures, the false comfort exposed before the "
                "event not during it"
            )
        return (
            f"{self.total_replicas()} replica(s) across "
            f"{len(self.replicas_per_rack)} rack(s), heaviest "
            f"{heaviest} holds {load}: survives "
            f"{tolerance} rack failure(s) at min-in-sync "
            f"{self.min_in_sync}{note}"
        )
