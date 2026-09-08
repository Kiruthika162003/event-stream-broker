"""Internal topic: the broker-side topics an app makes for itself, named to fit.

A stream application creates topics of its own behind the scenes:
repartition topics to move data to a new key, changelog topics to
back its state stores. These are internal, not meant for users to
produce to or consume from, and they follow conventions that keep
them from colliding and keep them correct. The name is prefixed
with the application id, so two applications each with a
repartition step do not share a topic and corrupt each other's
data, and the prefix also marks the topic as internal so tooling
can hide it and clean it up with the application rather than
leaving it orphaned. The partition count is not free to choose: a
repartition topic feeds a downstream that must be co-partitioned
with something, and a changelog must match the store's partitioning,
so the internal topic inherits the partition count of the source it
serves rather than a default, and creating it with a different
count would break the co-partitioning the topic exists to provide.
The manager builds the internal name from the application id and a
purpose, refuses a name that collides with an existing user topic,
because auto-creating over a user's topic would let the application
scribble on data it does not own, and refuses a partition count
that does not match the source, the co-partitioning break that
produces wrong results silently. It marks internal topics so they
are cleaned up when the application is deleted, and refuses to
auto-delete a topic not marked internal, because deleting a user
topic during an application teardown would destroy data the user
meant to keep. The report lists an application's internal topics,
because orphaned internal topics from deleted applications are a
common source of unexplained disk use that their prefix makes
easy to find.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class InternalTopicManager:
    app_id: str
    user_topics: set[str] = field(default_factory=set)
    internal: dict[str, int] = field(default_factory=dict)

    def name_for(self, purpose: str) -> str:
        return f"{self.app_id}-{purpose}"

    def create(self, purpose: str, partitions: int, source_partitions: int) -> str:
        name = self.name_for(purpose)
        if name in self.user_topics:
            raise Invalid(
                f"internal name '{name}' collides with a user topic; "
                "auto-creating over it would scribble on data the app "
                "does not own"
            )
        if partitions != source_partitions:
            raise Invalid(
                f"internal topic '{name}' has {partitions} partitions but "
                f"its source has {source_partitions}; the mismatch breaks "
                "co-partitioning and produces wrong results silently"
            )
        self.internal[name] = partitions
        return f"created internal topic '{name}' with {partitions} partition(s)"

    def delete(self, name: str) -> str:
        if name not in self.internal:
            raise Invalid(
                f"'{name}' is not marked internal; auto-deleting it during "
                "app teardown would destroy data the user meant to keep"
            )
        del self.internal[name]
        return f"deleted internal topic '{name}'"

    def owned(self) -> list[str]:
        return sorted(self.internal)
