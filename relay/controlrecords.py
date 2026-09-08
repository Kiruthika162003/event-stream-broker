"""Control records: the log carries markers that consumers must not see.

A transaction's commit or abort is itself recorded in the
partition log, as a control record, because the decision must be
as durable and replicated as the data it governs, living in the
same log means it survives exactly the failures the data
survives. But a control record is metadata, not data: it tells
the broker a transaction committed, and an ordinary consumer must
never receive it, because an application asking for its records
does not want transaction bookkeeping mixed into its stream. The
log therefore holds two kinds of record at the same offsets space,
data and control, and the fetch path filters control records out
of what it returns to consumers while still counting them in the
offset sequence, so offsets stay dense and a control record at
offset 500 means the consumer's next data record is at 501, not
that 500 is missing. This is the subtle part the naive
implementation gets wrong: skipping a control record must advance
the offset without yielding the record, and a consumer that
tracked its position by counting yielded records rather than by
offset would drift by one per control record and slowly lose its
place. The broker exposes control records only to the
transaction machinery and the admin tooling that debugs it,
never to the data path, and the filter is the boundary that keeps
the two audiences from seeing each other's records.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

DATA = "data"
COMMIT_MARKER = "commit"
ABORT_MARKER = "abort"
CONTROL_KINDS = (COMMIT_MARKER, ABORT_MARKER)


@dataclass(frozen=True)
class LogEntry:
    offset: int
    kind: str
    payload: bytes | None

    def is_control(self) -> bool:
        return self.kind in CONTROL_KINDS


def consumer_visible(
    entries: list[LogEntry],
) -> list[LogEntry]:
    return [e for e in entries if not e.is_control()]


def next_data_offset(
    entries: list[LogEntry], after: int
) -> int:
    for entry in sorted(entries, key=lambda e: e.offset):
        if entry.offset > after and not entry.is_control():
            return entry.offset
    raise Invalid(
        f"no data record after offset {after}; only control "
        "records remain, which consumers never receive"
    )


def offsets_stay_dense(entries: list[LogEntry]) -> bool:
    offsets = sorted(e.offset for e in entries)
    return all(
        expected == actual
        for expected, actual in enumerate(offsets, offsets[0])
    )


@dataclass
class ControlAudience:
    def for_data_path(self, entries: list[LogEntry]) -> str:
        control = sum(1 for e in entries if e.is_control())
        visible = len(consumer_visible(entries))
        return (
            f"{visible} data record(s) to the consumer, "
            f"{control} control record(s) filtered out; the "
            "offset sequence stays dense so no consumer drifts"
        )

    def for_admin(self, entries: list[LogEntry]) -> list[str]:
        return [
            f"offset {e.offset}: {e.kind} marker"
            for e in entries
            if e.is_control()
        ]
