"""Range assignment: align partitions across topics so joins stay local.

Round-robin spreads partitions evenly and destroys a property
some consumers depend on: co-partitioning. When two topics are
partitioned the same way by the same key, records for one key
land in the same partition number on both, and a consumer that
holds partition 3 of both can join them locally, in memory,
without a network shuffle. Round-robin assignment gives one
consumer partition 3 of topic A and another consumer partition
3 of topic B, and the join now spans two machines. The range
assignor preserves the alignment: it assigns each consumer the
same partition range across every subscribed topic, so a
consumer holding orders-3 also holds payments-3, and the join
stays on one machine. The cost is honest and stated: range
assignment is less balanced when topics have different partition
counts, the last consumer can get a fatter share, so the report
names the imbalance rather than hiding it, because a team that
chose co-partitioning should see what it paid, and a team that
did not need it should see it is overpaying.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


def range_assign(
    partitions: int, consumers: list[str]
) -> dict[str, list[int]]:
    if not consumers:
        raise Invalid("no consumers to assign to")
    consumers = sorted(consumers)
    per = partitions // len(consumers)
    extra = partitions % len(consumers)
    result: dict[str, list[int]] = {c: [] for c in consumers}
    offset = 0
    for index, consumer in enumerate(consumers):
        count = per + (1 if index < extra else 0)
        result[consumer] = list(range(offset, offset + count))
        offset += count
    return result


@dataclass
class MultiTopicAssignment:
    topic_partitions: dict[str, int]
    consumers: list[str]

    def assign(self) -> dict[str, dict[str, list[int]]]:
        result: dict[str, dict[str, list[int]]] = {
            c: {} for c in sorted(self.consumers)
        }
        for topic, count in self.topic_partitions.items():
            per_topic = range_assign(count, self.consumers)
            for consumer, parts in per_topic.items():
                result[consumer][topic] = parts
        return result

    def co_partitioned(
        self, consumer: str, topic_a: str, topic_b: str
    ) -> bool:
        assignment = self.assign()[consumer]
        return assignment.get(topic_a) == assignment.get(topic_b)

    def imbalance_report(self) -> str:
        assignment = self.assign()
        totals = {
            c: sum(len(p) for p in topics.values())
            for c, topics in assignment.items()
        }
        widest = max(totals.values())
        narrowest = min(totals.values())
        gap = widest - narrowest
        if gap == 0:
            return (
                "range assignment is perfectly balanced here; "
                "co-partitioning cost nothing this time"
            )
        return (
            f"range assignment spread {narrowest}..{widest} "
            f"partitions per consumer (gap {gap}); the price of "
            "co-partitioning, stated so a team sees what it paid "
            "or is overpaying for"
        )
