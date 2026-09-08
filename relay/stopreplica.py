"""Stop replica: stop hosting a partition, and keep or delete is not the same.

When a partition stops living on a broker the controller sends a
stop-replica instruction, and it carries a flag that changes
everything: stop and keep, or stop and delete. Stop-and-keep
happens when leadership or the replica set changed but this broker
still holds a valid copy that might be used again, so the broker
stops fetching and serving the partition but leaves the log on
disk, ready to resume without re-replicating from scratch. Stop-
and-delete happens when the partition is gone from this broker for
good, because the topic was deleted or the replica was reassigned
away, so the broker stops and removes the log, reclaiming the
disk. Confusing the two is expensive in both directions: deleting
when only asked to stop throws away a copy that would have avoided
a full re-replication if the partition comes back, and keeping when
asked to delete leaks disk that will never be used again and, for a
deleted topic, keeps data that was meant to be gone. The handler
applies the instruction according to the flag and refuses to delete
a replica it was only told to stop, treating a delete as requiring
the explicit delete flag rather than inferring it. It refuses to
act on a partition the broker does not host, an instruction for a
replica already gone, which is either a duplicate or a controller
working from stale state, and it refuses a stop for a partition
this broker currently leads without the leadership having moved
first, because stopping a live leader mid-serve drops its clients
rather than failing them over cleanly. The report states whether
the disk was reclaimed, because an operator expecting a deleted
topic to free space needs to know the delete flag actually reached
the brokers, not just that the topic vanished from metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid, Missing


@dataclass
class ReplicaHost:
    hosted: set[str] = field(default_factory=set)
    leading: set[str] = field(default_factory=set)
    on_disk: set[str] = field(default_factory=set)

    def stop_replica(self, partition: str, delete: bool) -> str:
        if partition not in self.hosted:
            raise Missing(
                f"partition {partition} is not hosted here; a stop for "
                "a replica already gone is a duplicate or stale controller"
            )
        if partition in self.leading:
            raise Invalid(
                f"partition {partition} is still led here; stopping a "
                "live leader drops its clients instead of failing them "
                "over, move leadership first"
            )
        self.hosted.discard(partition)
        if delete:
            self.on_disk.discard(partition)
            return f"stopped and deleted {partition}; disk reclaimed"
        return (
            f"stopped {partition}, log kept on disk; it can resume "
            "without re-replicating from scratch"
        )
