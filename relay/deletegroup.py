"""Delete group: a group with live members is not yours to delete.

Deleting a consumer group removes its committed offsets and the
coordinator's memory of it, which is the right cleanup for a group
no longer used, but it is destructive: a group's committed offsets
are where its consumers resume, so deleting them while consumers
still rely on them makes those consumers reset to the beginning or
the end on their next poll, reprocessing or skipping a whole
topic. The precondition that makes deletion safe is that the group
has no live members: an empty group has no consumer whose position
the offsets protect, so removing them harms no one, while a stable
group with members is actively using its offsets and deletion
would pull the floor out from under running consumers. The deleter
refuses a group that is not empty, naming the member count so the
operator sees the group is in use rather than getting a silent
failure, and it refuses a group already deleted, because a second
delete is either a mistake or a sign the operator is looking at
stale state. Deleting an empty group is idempotent in effect but
reported as a real deletion the first time and a no-op the second,
so a retry after a network timeout does not read as a surprise.
The deleter surfaces how many partitions' offsets the deletion
discards, because that number is the blast radius if the group
turns out to have been in use after all, and an operator deleting
a group with offsets for hundreds of partitions should be more
certain than one deleting a group with none.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid, Missing


@dataclass
class GroupRegistry:
    members: dict[str, int] = field(default_factory=dict)
    offset_partitions: dict[str, int] = field(default_factory=dict)
    deleted: set[str] = field(default_factory=set)

    def delete(self, group_id: str) -> str:
        if group_id in self.deleted:
            raise Invalid(
                f"group '{group_id}' is already deleted; a second "
                "delete is a mistake or stale state"
            )
        if group_id not in self.members:
            raise Missing(f"no group '{group_id}' to delete")
        live = self.members[group_id]
        if live > 0:
            raise Invalid(
                f"group '{group_id}' has {live} live member(s); "
                "deleting its offsets would pull the floor out from "
                "under running consumers, resetting them"
            )
        discarded = self.offset_partitions.get(group_id, 0)
        self.deleted.add(group_id)
        del self.members[group_id]
        self.offset_partitions.pop(group_id, None)
        return (
            f"deleted '{group_id}', discarding offsets for "
            f"{discarded} partition(s); that is the blast radius if "
            "it turns out to have been in use"
        )
