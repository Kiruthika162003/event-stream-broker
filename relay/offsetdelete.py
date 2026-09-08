"""Offset delete: drop the offsets for topics the group left, not ones it uses.

A long-lived consumer group accumulates committed offsets for
every partition it has ever consumed, and when it stops consuming
a topic those offsets linger, holding position for a partition no
member reads any more and counting against the offsets topic
forever. OffsetDelete cleans exactly those: it removes the
committed offset for specific partitions while leaving the group
itself and its other offsets intact, which is the difference from
deleting the whole group. The precondition is per partition, not
per group: an offset may be deleted only for a partition no live
member is currently assigned, because deleting the offset of a
partition a member is actively consuming would reset that member
mid-stream on its next commit, the same harm as deleting a live
group but scoped to one partition. The deleter refuses a partition
that a member still owns, naming the member, because the operator
believing a topic was abandoned may be wrong about one partition
still assigned through a stale subscription. It distinguishes a
partition with no committed offset, where deletion is a harmless
no-op, from one actively owned, where deletion is refused, so a
bulk cleanup does not fail wholesale because a few partitions had
nothing to delete. The report counts deleted against skipped and
refused, because a cleanup that refused most of its partitions
means the group is more active than the operator thought and the
topic was not abandoned after all.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class OffsetDeleter:
    committed: dict[str, int] = field(default_factory=dict)
    owned: set[str] = field(default_factory=set)

    def delete(self, partition: str) -> str:
        if partition in self.owned:
            raise Invalid(
                f"partition {partition} is owned by a live member; "
                "deleting its offset would reset that member "
                "mid-stream on its next commit"
            )
        if partition not in self.committed:
            return f"{partition}: no committed offset, nothing to delete"
        del self.committed[partition]
        return f"{partition}: offset deleted"

    def delete_many(self, partitions: list[str]) -> str:
        deleted = skipped = refused = 0
        for p in partitions:
            try:
                result = self.delete(p)
            except Invalid:
                refused += 1
                continue
            if "deleted" in result:
                deleted += 1
            else:
                skipped += 1
        return (
            f"{deleted} deleted, {skipped} already empty, {refused} "
            "refused as still owned; many refused means the group is "
            "more active than thought and the topic was not abandoned"
        )
