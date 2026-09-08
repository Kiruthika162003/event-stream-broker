"""Session window: activity clusters into sessions, and a gap ends one.

A session window groups records not by a fixed clock boundary but
by activity: records close together in time belong to the same
session, and a gap of inactivity longer than the session gap ends
one session and starts the next. This fits data that comes in
bursts, a user's clicks in one visit, a device's readings while
awake, where the meaningful unit is the burst, not a fixed minute.
A session is defined by its first and last record's times, and a
new record extends the session if it falls within the gap of the
session's current end, pushing the end out, or starts a new session
if it falls beyond the gap. The subtle case is a record that lands
between two existing sessions and is within the gap of both: it
bridges them, and the two sessions plus the bridging record merge
into one, because the inactivity that separated them turned out not
to be inactivity once the bridging record arrived. This merge is
what makes session windows harder than fixed windows: a late record
can join two sessions that were already emitted separately,
requiring their results to be retracted and replaced with the
merged one. The window refuses a non-positive gap, which would make
every record its own session or all records one session, and it
keeps sessions ordered by time so the bridge check only has to look
at neighbors. The report states how many sessions a stream of
records collapsed into, because a gap set too large merges distinct
bursts into one session that spans them, and a gap too small splits
one burst into many, and the session count against the record count
is the signal of which.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class SessionWindows:
    gap: int
    sessions: list[list[int]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.gap < 1:
            raise Invalid(
                "the session gap must be positive; zero makes every "
                "record its own session"
            )

    def _within(self, session: list[int], time: int) -> bool:
        return session[0] - self.gap <= time <= session[-1] + self.gap

    def add(self, time: int) -> None:
        touching = [s for s in self.sessions if self._within(s, time)]
        others = [s for s in self.sessions if not self._within(s, time)]
        merged = sorted([t for s in touching for t in s] + [time])
        others.append(merged)
        self.sessions = sorted(others, key=lambda s: s[0])

    def session_bounds(self) -> list[tuple[int, int]]:
        return [(s[0], s[-1]) for s in self.sessions]

    def report(self, record_count: int) -> str:
        n = len(self.sessions)
        return (
            f"{record_count} record(s) collapsed into {n} session(s); "
            "too large a gap merges distinct bursts, too small splits "
            "one burst, and this count is the signal of which"
        )
