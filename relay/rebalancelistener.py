"""Rebalance listener: the callback contract that lets a consumer let go cleanly.

When a rebalance moves a partition away from a consumer, the
consumer needs a chance to finish what it was doing with that
partition before it loses it, and the rebalance listener is that
chance. It has two callbacks with a strict ordering. Before the
partition is revoked, on-revoke fires, and this is where the
consumer commits its final offset for the partition and flushes
any state it accumulated, because after revoke the partition
belongs to someone else and a late commit would be against an
assignment the consumer no longer holds. After the new
assignment, on-assign fires, and this is where the consumer
initializes state for partitions it gained, seeking to the
committed offset and loading any local cache. The ordering is the
whole contract: on-revoke must complete before the partition is
reassigned, because a consumer that has not finished committing
when the partition moves to another consumer creates a window
where the offset is ambiguous and the new owner may reprocess or
skip. The listener enforces that on-revoke's commit happens while
the consumer still owns the partition, refusing a commit after
revoke completed, because that commit is the exact race the
ordered callbacks exist to close. A listener whose on-revoke
throws is a consumer that could not clean up, and the rebalance
proceeds anyway rather than stalling the whole group on one
member's cleanup bug, but the failure is recorded, because a
member that consistently fails on-revoke is losing state on every
rebalance and slowly corrupting its output.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class RebalanceListener:
    owned: set[int] = field(default_factory=set)
    revoke_committed: dict[int, int] = field(default_factory=dict)
    revoke_failures: int = 0
    phase: str = "stable"

    def begin_revoke(self, partitions: set[int]) -> str:
        if not partitions <= self.owned:
            raise Invalid(
                "cannot revoke partitions not owned; the "
                "listener acts only on what it holds"
            )
        self.phase = "revoking"
        return f"on-revoke for {sorted(partitions)}: commit now"

    def commit_on_revoke(
        self, partition: int, offset: int
    ) -> str:
        if self.phase != "revoking":
            raise Invalid(
                f"partition {partition} commit after revoke "
                "completed is the exact race the ordered "
                "callbacks close"
            )
        if partition not in self.owned:
            raise Invalid(
                f"partition {partition} is not owned"
            )
        self.revoke_committed[partition] = offset
        return f"partition {partition} committed at {offset} before release"

    def complete_revoke(self, partitions: set[int]) -> str:
        self.owned -= partitions
        self.phase = "stable"
        return f"released {sorted(partitions)}"

    def on_assign(self, partitions: set[int]) -> str:
        self.owned |= partitions
        self.phase = "stable"
        return (
            f"on-assign for {sorted(partitions)}: seek to "
            "committed and load state"
        )

    def revoke_threw(self) -> str:
        self.revoke_failures += 1
        self.phase = "stable"
        return (
            "on-revoke failed; the rebalance proceeds so one "
            "member's cleanup bug does not stall the group, but "
            "a member failing this consistently corrupts its "
            "output"
        )
