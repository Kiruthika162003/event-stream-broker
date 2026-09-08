"""Hinted handoff: hold a down replica's writes, replay them when it returns.

When a write should go to a replica that is temporarily down,
dropping it would lose durability and blocking would stall the
write, so hinted handoff takes a third path: another node accepts
the write on the down replica's behalf and stores it as a hint, a
note saying this write belongs to that replica, and when the replica
recovers the hints are replayed to it, catching it up on what it
missed while down. This keeps writes flowing during a brief outage
and heals the replica quickly on return, without waiting for the
slower anti-entropy reconciliation to notice the gap. The hint has a
time limit, because holding hints for a replica that never comes
back would grow unbounded, so a hint older than its window is
dropped, and if a replica is down long enough for its hints to
expire, it comes back missing those writes and anti-entropy, the
merkle-tree reconciliation, must catch them later. This is the
division of labor: hinted handoff handles brief outages cheaply and
promptly, anti-entropy is the backstop for outages that outlast the
hints. The store accepts a hint for a down replica, replays hints
on recovery in the order they were stored so the replica applies
them like a normal write stream, expires hints past their window,
and refuses a hint for a replica that is up, which should take the
write directly rather than through a hint that adds a hop. It
reports the pending hint count per replica, because a replica
accumulating many hints is one down long enough that its hints may
start expiring, the point where anti-entropy rather than handoff
becomes the thing that will heal it."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class HintedHandoff:
    hint_window: int
    hints: dict[str, list[tuple[int, str]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.hint_window < 1:
            raise Invalid("the hint window must be positive")

    def store_hint(self, replica: str, now: int, write: str, replica_up: bool) -> str:
        if replica_up:
            raise Invalid(
                f"replica '{replica}' is up; it should take the write directly, "
                "not through a hint that adds a hop"
            )
        self.hints.setdefault(replica, []).append((now, write))
        return f"hint stored for down replica '{replica}'"

    def _expire(self, replica: str, now: int) -> None:
        kept = [(t, w) for t, w in self.hints.get(replica, []) if now - t < self.hint_window]
        self.hints[replica] = kept

    def replay(self, replica: str, now: int) -> list[str]:
        self._expire(replica, now)
        writes = [w for _t, w in self.hints.get(replica, [])]
        self.hints[replica] = []
        return writes

    def pending(self, replica: str, now: int) -> str:
        self._expire(replica, now)
        n = len(self.hints.get(replica, []))
        return (
            f"{n} hint(s) pending for '{replica}'; many means it is down long "
            "enough that hints may expire, where anti-entropy rather than "
            "handoff becomes what heals it"
        )
