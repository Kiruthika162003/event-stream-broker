"""Temporal join: enrich a record with the table as it was then, not as it is now.

Joining a stream to reference data usually means looking up the
table's current value, but that is wrong when the record is old and
the reference data has changed since. Enriching a trade with the
exchange rate should use the rate that was in effect at the trade's
time, not today's, and a late-arriving trade from last week should
still get last week's rate. A temporal, or as-of, join does that:
the table keeps versioned values, each with the time it took effect,
and a stream record joins the version that was current at the
record's event time, the latest table version whose effective time
is at or before the record's timestamp. This makes the enrichment
correct regardless of when the record arrives, because it looks up
by the record's own time, not the wall clock, so a replayed or late
record gets the same answer it would have gotten in real time. The
join finds the applicable version by searching the table's versions
for the newest one not after the record's timestamp, the same floor
search an offset index does, and a record older than the table's
first version has no applicable value, since the reference data did
not exist yet. The joiner records versioned table values in time
order, joins a record to the floor version at its timestamp, and
refuses a record whose timestamp predates the first version, a
lookup into a table that had no value then. It reports how far back
the joined version was, because a stream routinely joining old
versions is one whose records lag the reference data, an event-time
skew worth knowing since the current-value join would have silently
given the wrong, too-new answer."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid, Missing


@dataclass
class TemporalJoin:
    # (effective_time, value), kept in increasing time order
    versions: list[tuple[int, str]] = field(default_factory=list)

    def add_version(self, effective_time: int, value: str) -> None:
        if self.versions and effective_time <= self.versions[-1][0]:
            raise Invalid(
                "versions must be added in increasing effective-time order"
            )
        self.versions.append((effective_time, value))

    def join(self, event_time: int) -> str:
        if not self.versions or event_time < self.versions[0][0]:
            raise Missing(
                f"no table version at or before {event_time}; the reference "
                "data did not exist yet, a current-value join would give a "
                "wrong too-new answer"
            )
        applicable = self.versions[0][1]
        for eff, value in self.versions:
            if eff <= event_time:
                applicable = value
            else:
                break
        return applicable

    def staleness(self, event_time: int) -> str:
        # how far back the joined version's effective time is
        eff = None
        for e, _v in self.versions:
            if e <= event_time:
                eff = e
            else:
                break
        if eff is None:
            return "no applicable version"
        back = event_time - eff
        return (
            f"joined a version effective {back} before the record; a stream "
            "routinely joining old versions lags the reference data, where a "
            "current-value join would silently give a too-new answer"
        )
