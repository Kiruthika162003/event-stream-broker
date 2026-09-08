"""Fetch sessions: after the first full fetch, send only what changed.

A consumer subscribed to a thousand partitions sends a fetch
request naming all thousand every round, and most rounds most
partitions have nothing new, so the request and its empty
responses are almost all overhead. The incremental fetch session
fixes it: the first fetch is full and establishes a session, and
subsequent fetches in that session name only the partitions whose
desired offset changed, with the broker remembering the rest. The
broker responds with only the partitions that actually have new
data, so a consumer polling a thousand mostly-idle partitions
exchanges a handful of bytes instead of a thousand entries. The
session is identified and epoched: each incremental fetch carries
the session's expected epoch, and a mismatch, from a broker
restart that forgot the session or a confused client, forces a
full fetch to resynchronize rather than serving a partial view
against stale session state, because an incremental fetch against
a session the broker no longer holds correctly would silently
skip partitions. The report states the compression ratio of the
protocol itself, entries sent against partitions subscribed,
because that number is the entire reason the session exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class FetchSession:
    session_id: int
    epoch: int = 0
    known_offsets: dict[int, int] = field(default_factory=dict)

    def full_fetch(self, offsets: dict[int, int]) -> str:
        self.known_offsets = dict(offsets)
        self.epoch = 1
        return (
            f"session {self.session_id} established at epoch 1 "
            f"with {len(offsets)} partition(s)"
        )

    def incremental_fetch(
        self, epoch: int, changed: dict[int, int]
    ) -> tuple[list[int], str]:
        if self.epoch == 0:
            raise Invalid(
                "no session yet; the first fetch must be full"
            )
        if epoch != self.epoch:
            raise Invalid(
                f"epoch mismatch: client has {epoch}, session is "
                f"at {self.epoch}; forcing a full fetch to "
                "resync, because a partial view against stale "
                "session state silently skips partitions"
            )
        self.known_offsets.update(changed)
        self.epoch += 1
        touched = sorted(changed)
        return touched, (
            f"{len(touched)} of {len(self.known_offsets)} "
            "partition(s) named; the rest the broker remembers"
        )

    def protocol_ratio(
        self, subscribed: int, entries_sent: int
    ) -> str:
        if subscribed < 1:
            raise Invalid("no subscription to measure")
        saved = subscribed - entries_sent
        return (
            f"{entries_sent} entrie(s) for {subscribed} "
            f"partition(s), {saved} elided; the elision is the "
            "entire reason the session exists"
        )
