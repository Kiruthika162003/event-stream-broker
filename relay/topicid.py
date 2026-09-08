"""Topic id: a name can be reused, an identity cannot, and requests trust the id.

A topic has a name, but a name is not a stable identity, because a
topic can be deleted and a new one created with the same name, and
the two are different topics that happen to share a label: the
second has none of the first's data, partitions, or history. When
requests and metadata refer to a topic only by name, a client
holding stale metadata from before a delete-and-recreate can send a
request meant for the old topic to the new one, reading or writing
the wrong data under a name it trusts. A topic id fixes this by
giving each topic a unique identifier at creation that never
changes and is never reused, so a request carrying a topic id is
checked against the topic that id names, and a request for a
deleted topic's id is rejected as unknown rather than silently
served by the same-named replacement. The registry assigns an id
at creation and refuses to resolve an id that does not exist, which
is what a stale client's request for a recreated topic looks like,
telling it to refresh its metadata rather than acting on the wrong
topic. Resolving by name still works for clients that predate topic
ids, but the registry surfaces when a name now maps to a different
id than a client last saw, because that mismatch is the recreate
the id was invented to catch. The registry refuses to create a
topic whose name is already live, since two live topics of one name
would make name resolution ambiguous, and it keeps a deleted
topic's id tombstoned so it is never handed to a new topic, because
reusing an id would resurrect the exact confusion the id prevents.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid, Missing


@dataclass
class TopicRegistry:
    _next: int = 1
    by_name: dict[str, int] = field(default_factory=dict)
    live_ids: set[int] = field(default_factory=set)
    retired_ids: set[int] = field(default_factory=set)

    def create(self, name: str) -> int:
        if name in self.by_name:
            raise Invalid(
                f"topic '{name}' is already live; two live topics of "
                "one name make name resolution ambiguous"
            )
        topic_id = self._next
        self._next += 1
        self.by_name[name] = topic_id
        self.live_ids.add(topic_id)
        return topic_id

    def delete(self, name: str) -> None:
        if name not in self.by_name:
            raise Missing(f"no live topic '{name}' to delete")
        topic_id = self.by_name.pop(name)
        self.live_ids.discard(topic_id)
        self.retired_ids.add(topic_id)

    def resolve_id(self, topic_id: int) -> str:
        if topic_id not in self.live_ids:
            raise Missing(
                f"topic id {topic_id} is unknown; it was deleted, and "
                "a same-named replacement has a different id, so "
                "refresh metadata rather than acting on the wrong topic"
            )
        for name, tid in self.by_name.items():
            if tid == topic_id:
                return name
        raise Missing(f"topic id {topic_id} not found")

    def is_recreated(self, name: str, client_saw_id: int) -> bool:
        current = self.by_name.get(name)
        return current is not None and current != client_saw_id
