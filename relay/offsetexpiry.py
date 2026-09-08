"""Offset expiration: forget a group's position, but only if it truly left.

The offset store keeps a committed position per group-partition,
and groups come and go, so old positions must expire or the store
grows forever with the ghosts of consumers that ran once in 2019.
Expiration is dangerous because it is irreversible: expire an
active group's offset and it resets on its next poll, replaying or
skipping depending on its reset policy, so the rule is that only a
group with no active members and no commit within the retention
window expires. An active group, even one that has not committed
recently because its partition is idle, is never expired, because
idle is not gone, and expiring an idle-but-live group is the same
data-correctness bug as a too-short retention. The expiry uses
last-commit time and current membership together, both conditions
required, because either alone is wrong: last-commit alone expires
a live group parked on a quiet partition, and membership alone
never expires a group whose members all crashed without
unsubscribing. The report names how many offsets expired and how
much store they freed, since a store that never expires anything
is leaking and one that expires active groups is losing data, and
the healthy number is a small nonzero.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class GroupOffset:
    group: str
    partition: int
    committed_offset: int
    last_commit_tick: int


@dataclass
class OffsetExpirer:
    retention_ticks: int
    expired: int = 0
    freed_entries: int = 0
    protected_active: int = 0

    def __post_init__(self) -> None:
        if self.retention_ticks < 1:
            raise Invalid("the retention window must be positive")

    def sweep(
        self,
        offsets: list[GroupOffset],
        active_groups: set[str],
        now: int,
    ) -> list[GroupOffset]:
        survivors = []
        for entry in offsets:
            if entry.group in active_groups:
                self.protected_active += 1
                survivors.append(entry)
                continue
            if now - entry.last_commit_tick <= self.retention_ticks:
                survivors.append(entry)
                continue
            self.expired += 1
            self.freed_entries += 1
        return survivors

    def report(self) -> str:
        if self.expired == 0 and self.protected_active == 0:
            return "nothing swept yet"
        return (
            f"{self.expired} offset(s) expired freeing "
            f"{self.freed_entries} entrie(s), "
            f"{self.protected_active} active group(s) protected; "
            "a store that expires nothing leaks and one that "
            "expires active groups loses data, so healthy is a "
            "small nonzero"
        )
