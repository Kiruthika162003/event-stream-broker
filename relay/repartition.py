"""Repartition: change the key, and the data must physically move to match.

A stream partitioned by one key sometimes needs to be grouped or
joined by a different key, and changing the key is not just
relabeling: it changes which partition a record belongs to, because
the partition is chosen by hashing the key. A record keyed by user
that must now be grouped by country cannot stay where it is, since
records for one country are scattered across every partition by
their old user key, so the stream is repartitioned: each record is
written to an internal topic keyed by the new key, and the hashing
of that new key sends every same-country record to the same
partition of the internal topic, where a downstream task can group
them locally. This is why a key-changing operation followed by an
aggregation forces a repartition topic: the aggregation needs all
values for a key on one task, and only routing through a topic
keyed by that key achieves it. The repartitioner computes the
target partition from the new key and refuses to let a downstream
grouping read from a stream that changed its key without a
repartition, because grouping a mis-partitioned stream would sum
each key's values separately on every task and produce as many
partial results as partitions, none of them the real total. The
internal topic's partition count sets the downstream parallelism,
so the repartitioner refuses a partition count of zero and reports
when records for one key spread across partitions, the signature of
a key that was not actually repartitioned. The report states the
shuffle cost, the fraction of records that changed partition,
because repartitioning writes every record back to a topic and
reads it again, doubling the traffic for that step, a cost worth
seeing before adding a key change casually.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class Repartitioner:
    partitions: int
    routed: dict[str, set[int]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.partitions < 1:
            raise Invalid("a repartition topic needs at least one partition")

    def partition_for(self, new_key: str) -> int:
        target = (hash(new_key) & 0x7FFFFFFF) % self.partitions
        self.routed.setdefault(new_key, set()).add(target)
        return target

    def is_grouping_safe(self, new_key: str) -> bool:
        return len(self.routed.get(new_key, set())) <= 1

    def require_grouping_safe(self, new_key: str) -> None:
        if not self.is_grouping_safe(new_key):
            raise Invalid(
                f"key '{new_key}' spread across "
                f"{len(self.routed[new_key])} partitions; grouping a "
                "mis-partitioned stream sums it separately per task and "
                "yields partial totals, none the real one"
            )

    def shuffle_cost(self, changed: int, total: int) -> str:
        if total == 0:
            return "no records; no shuffle"
        pct = changed / total * 100
        return (
            f"{changed}/{total} record(s) changed partition ({pct:.0f}%); "
            "a repartition writes every record back to a topic and reads "
            "it again, doubling the traffic for that step"
        )
