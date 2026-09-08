"""A first stream: produce, commit, consume, and the watermark in between.

Run with: python -m examples.firststream
"""

from __future__ import annotations

from relay.consumergroup import ConsumerGroup
from relay.records import Record
from relay.topics import TopicRegistry


def main() -> int:
    registry = TopicRegistry()
    orders = registry.create("orders", partition_count=3)

    for partition in orders.partitions:
        for number in range(4):
            partition.append(
                Record(value=f"p{partition.number}-order-{number}".encode())
            )
    placement = {
        partition.number: partition.log.next_offset()
        for partition in orders.partitions
    }
    print(f"produce: 4 records per partition -> {placement}")

    for partition in orders.partitions:
        partition.advance_watermark(
            partition.log.next_offset() - 1
        )
    committed = {
        partition.number: partition.high_watermark
        for partition in orders.partitions
    }
    print(f"commit:  watermarks at {committed}")
    print(
        "         each partition holds one uncommitted record: "
        + ", ".join(
            partition.honesty_interval().split(": ")[1]
            for partition in orders.partitions
        )
    )

    group = ConsumerGroup(
        name="fulfilment", contract="at-least-once"
    )
    print(f"consume: {group.contract_line()}")
    read = 0
    for partition in orders.partitions:
        for offset in range(partition.high_watermark):
            partition.consume(offset)
            read += 1
        group.commit(partition, partition.high_watermark)
    print(
        f"         read {read} committed records, "
        f"lag now {sum(group.lag(p) for p in orders.partitions)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
