"""Topics: named streams whose partition count is a promise about order.

A topic is a name over N partitions, and N is the most
permanent decision its creator makes: keyed records route by
hash of key modulo N, so all events for one key land in one
partition and arrive in order, and changing N later reshuffles
every key's home, silently breaking the per-key ordering that
consumers built their logic on. The registry therefore treats
partition count as immutable and says why at the refusal,
offering the honest alternative, a new topic and a migration,
instead of the quiet remap that turns yesterday's order into
this morning's incident. Unkeyed records round-robin for
balance, keyed records hash for order, and the router can
always answer the audit question: which partition does this
key live in, and would it have lived there last month.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from relay.errors import Invalid, Missing
from relay.partition import Partition
from relay.records import Record


def _key_slot(key: bytes, partitions: int) -> int:
    digest = hashlib.sha256(key).hexdigest()
    return int(digest[:8], 16) % partitions


@dataclass
class Topic:
    name: str
    partitions: list[Partition]
    round_robin_next: int = 0

    def route(self, record: Record) -> int:
        if record.key is not None:
            return _key_slot(record.key, len(self.partitions))
        slot = self.round_robin_next
        self.round_robin_next = (slot + 1) % len(
            self.partitions
        )
        return slot

    def append(self, record: Record) -> tuple[int, int]:
        slot = self.route(record)
        offset = self.partitions[slot].append(record)
        return slot, offset


@dataclass
class TopicRegistry:
    topics: dict[str, Topic] = field(default_factory=dict)

    def create(self, name: str, partition_count: int) -> Topic:
        if not name.strip() or "/" in name:
            raise Invalid(
                "topic names are single path-free words"
            )
        if name in self.topics:
            raise Invalid(f"topic {name} already exists")
        if partition_count < 1:
            raise Invalid("a topic needs at least one partition")
        topic = Topic(
            name=name,
            partitions=[
                Partition(number=number)
                for number in range(partition_count)
            ],
        )
        self.topics[name] = topic
        return topic

    def get(self, name: str) -> Topic:
        topic = self.topics.get(name)
        if topic is None:
            raise Missing(f"topic {name} does not exist")
        return topic

    def resize(self, name: str, new_count: int) -> str:
        topic = self.get(name)
        raise Invalid(
            f"{name} has {len(topic.partitions)} partition(s) "
            f"and will keep them: resizing to {new_count} "
            "reshuffles every key's home and breaks per-key "
            "order silently; create a new topic and migrate, "
            "which is the same work done honestly"
        )

    def audit_key(self, name: str, key: bytes) -> str:
        topic = self.get(name)
        slot = _key_slot(key, len(topic.partitions))
        return (
            f"{key!r} lives in partition {slot} of {name}, "
            "and lived there last month too, because the "
            "count is immutable"
        )
