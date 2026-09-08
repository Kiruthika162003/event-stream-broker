"""Connector offset: a source's own position, committed only once it is safe.

A source connector reads from an external system, a database change
log, a file, an API cursor, and writes what it reads into the
broker, and to resume after a restart without re-reading everything
it must remember where it was in the source. That position is not a
broker offset, it is the source's own, a binlog coordinate or a file
byte position, opaque to the broker, and the connector tracks it
alongside the records it produces. The rule that keeps it correct
is the order of commit: the connector may commit a source position
only once every record up to that position has been acknowledged by
the broker, because committing earlier would, after a crash, resume
the source past records that never made it into the broker, losing
them silently. So the connector holds the source position of each
in-flight record, and advances its committed source position only
to the point where the broker has acknowledged everything before
it, which may lag the latest read while records are still in flight.
This gives at-least-once from the source: a crash resumes from the
last committed source position and re-reads anything produced but
not yet committed, so the broker may see duplicates, which a
downstream deduplicates, but never a gap. The tracker records a
read with its source position, marks records acknowledged, and
commits the source position up to the acknowledged prefix, refusing
to commit past an unacknowledged record, the gap that would lose
data. It reports the committed source position against the latest
read, because a committed position far behind the read is a
connector with many records in flight to the broker, a backlog that
grows the re-read on a crash."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class ConnectorOffsets:
    # source_position -> acknowledged?
    inflight: dict[int, bool] = field(default_factory=dict)
    committed: int = -1
    latest_read: int = -1

    def read(self, source_position: int) -> None:
        if source_position <= self.latest_read:
            raise Invalid(
                f"source position {source_position} does not advance past "
                f"the latest read {self.latest_read}; positions only move "
                "forward"
            )
        self.inflight[source_position] = False
        self.latest_read = source_position

    def acknowledge(self, source_position: int) -> None:
        if source_position not in self.inflight:
            raise Invalid(f"no in-flight record at source position {source_position}")
        self.inflight[source_position] = True

    def commit(self) -> int:
        # advance over the contiguous acknowledged prefix
        positions = sorted(self.inflight)
        for pos in positions:
            if self.inflight[pos]:
                self.committed = pos
                del self.inflight[pos]
            else:
                break
        return self.committed

    def resume_from(self) -> int:
        return self.committed

    def report(self) -> str:
        behind = self.latest_read - self.committed
        return (
            f"committed source position {self.committed}, latest read "
            f"{self.latest_read}, {behind} in flight; a large gap is a "
            "backlog to the broker that grows the re-read on a crash"
        )
