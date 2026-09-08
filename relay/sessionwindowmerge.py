"""Session window merge: a bridging event fuses two sessions into one.

A session window groups events for a key that arrive close together
and closes the window after a gap of inactivity. Unlike a fixed window,
a session has no predetermined bounds; it grows to fit the events, and
its edges are defined by the events themselves plus the inactivity gap
on either side. That flexibility creates a case fixed windows never
have: an event can arrive that belongs to two existing sessions at
once. If two sessions sit with a quiet stretch between them, slightly
wider than the gap so they stayed separate, and then a late event lands
in that stretch, within a gap of the end of the earlier session and
within a gap of the start of the later one, it bridges them, and the
correct result is not a third tiny session but one merged session
spanning both plus the new event. Merging means the two old sessions
are removed and replaced by a single window from the earliest start to
the latest end, carrying the combined event count, because the events
were always one burst of activity that only looked like two while the
bridge was missing. Getting this wrong, leaving the sessions separate
or creating a nested third, double counts or fragments the activity a
session was meant to capture whole. The merger holds the sessions for a
key ordered by start, adds an event by finding every session the event
is within a gap of, and if more than one, fuses them and the event into
one spanning session. It refuses a non-positive gap, because a session
with no inactivity threshold never closes, and reports the session
count, because a key whose sessions keep merging is one long continuous
activity, where a key with many small sessions is bursty with real
quiet between."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class _Session:
    start: int
    end: int
    count: int


@dataclass
class SessionWindowMerge:
    gap: int
    sessions: list[_Session] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.gap <= 0:
            raise Invalid("the gap must be positive; a session must be able to close")

    def add_event(self, timestamp: int) -> None:
        # a session is touched if the event falls within a gap of its span
        touched = [
            s
            for s in self.sessions
            if s.start - self.gap <= timestamp <= s.end + self.gap
        ]
        if not touched:
            self.sessions.append(_Session(start=timestamp, end=timestamp, count=1))
        else:
            start = min([s.start for s in touched] + [timestamp])
            end = max([s.end for s in touched] + [timestamp])
            count = sum(s.count for s in touched) + 1
            for s in touched:
                self.sessions.remove(s)
            self.sessions.append(_Session(start=start, end=end, count=count))
        self.sessions.sort(key=lambda s: s.start)

    def spans(self) -> list[tuple[int, int, int]]:
        return [(s.start, s.end, s.count) for s in self.sessions]

    def note(self) -> str:
        n = len(self.sessions)
        return (
            f"{n} session(s) for this key; a key whose sessions keep merging is "
            "one long continuous activity, many small sessions is bursty with "
            "real quiet between"
        )
