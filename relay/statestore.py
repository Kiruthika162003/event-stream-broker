"""State store: local state that survives a crash because a topic remembers it.

A stream processor keeps local state, a running count per key, a
join buffer, and that state lives on the instance processing the
partition, so if the instance dies the state dies with it unless it
was written down somewhere durable. The somewhere is a changelog
topic: every update to the state store is also appended to a
changelog, a compacted topic keyed the same as the store, so the
changelog always holds the latest value per key and the store is
exactly the changelog folded into a map. This makes recovery a
replay: a new instance taking over the partition rebuilds the store
by reading the changelog from the start to the end, applying each
record, and only once it has caught up to the changelog's end is
the store current and safe to serve. Serving reads before restore
finishes would answer from a partial state, missing every key whose
last update is in the unread tail, so the store refuses reads while
restoring. The write path is write-ahead in spirit: the changelog
append must be acknowledged before the state is considered durably
updated, because a store updated locally but not yet in the
changelog would lose that update on a crash, the exact gap the
changelog exists to close. The store refuses to apply a changelog
record out of offset order during restore, because the changelog is
the source of truth and applying it out of order could leave an
older value shadowing a newer one. The report states how far
restore has progressed, because a takeover blocked on a long
changelog replay is a store whose changelog was not compacting
fast enough, leaving more to replay than the live key count needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class StateStore:
    changelog_end: int
    restored_to: int = 0
    ready: bool = False
    data: dict[str, int] = field(default_factory=dict)

    def apply_changelog(self, offset: int, key: str, value: int) -> None:
        if offset < self.restored_to:
            raise Invalid(
                f"changelog offset {offset} is behind {self.restored_to}; "
                "applying out of order could shadow a newer value with "
                "an older one"
            )
        self.data[key] = value
        self.restored_to = offset + 1
        if self.restored_to >= self.changelog_end:
            self.ready = True

    def read(self, key: str) -> int:
        if not self.ready:
            raise Invalid(
                f"restore is at {self.restored_to}/{self.changelog_end}; "
                "reading now would miss keys whose last update is in the "
                "unread tail"
            )
        return self.data.get(key, 0)

    def write(self, key: str, value: int, changelog_acked: bool) -> str:
        if not changelog_acked:
            raise Invalid(
                "the changelog append is not acknowledged; a local "
                "update not yet in the changelog would be lost on a "
                "crash, the gap the changelog exists to close"
            )
        self.data[key] = value
        self.changelog_end += 1
        self.restored_to = self.changelog_end
        return f"{key}={value} durable, changelog end {self.changelog_end}"

    def restore_progress(self) -> str:
        return (
            f"restored {self.restored_to}/{self.changelog_end}; a long "
            "replay means the changelog was not compacting fast enough, "
            "more to replay than the live key count needs"
        )
