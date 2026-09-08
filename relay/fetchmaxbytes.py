"""Per-partition fetch cap: one hot partition must not eat the whole response.

A fetch has an overall response budget, but it also needs a
per-partition cap, because without one a single hot partition
with a huge backlog fills the entire response and the consumer's
other partitions get nothing, starving them behind the busy one.
The per-partition cap bounds how much any single partition can
contribute, so the response is shared and every partition makes
some progress each fetch, the same fairness the fetch assembler
provides across partitions, enforced here as a ceiling per
partition rather than a rotation. The interaction with the
oversized-record rule is the subtle part: a per-partition cap
smaller than a single record would starve that partition
forever, its one record never fitting the cap, so the cap must
yield to the oversized-record exception exactly as the overall
budget does, returning the one large record alone even though it
exceeds the per-partition cap. The resolver computes each
partition's allocation as the smaller of its available data and
the per-partition cap, except where a single record exceeds the
cap, and it reports which partitions were capped, because a
partition consistently hitting its cap has more backlog than the
cap admits per fetch and is falling behind within the fetch
itself, a signal that either the cap is too tight for this
workload or the partition needs its own consumer, which a total-
bytes-only view would never reveal.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class PerPartitionCap:
    per_partition_max: int

    def __post_init__(self) -> None:
        if self.per_partition_max < 1:
            raise Invalid("the per-partition cap must be positive")

    def allocate(
        self, partition: int, available: int, largest_record: int
    ) -> tuple[int, str]:
        if available == 0:
            return 0, f"partition {partition}: nothing available"
        if largest_record > self.per_partition_max:
            return largest_record, (
                f"partition {partition}: one record of "
                f"{largest_record} exceeds the cap "
                f"{self.per_partition_max}, returned alone so it "
                "does not starve forever"
            )
        allotted = min(available, self.per_partition_max)
        if allotted < available:
            return allotted, (
                f"partition {partition}: capped at "
                f"{self.per_partition_max} of {available}, "
                "falling behind within the fetch, too tight for "
                "this workload or needs its own consumer"
            )
        return allotted, (
            f"partition {partition}: all {available} fit under the "
            "cap"
        )
