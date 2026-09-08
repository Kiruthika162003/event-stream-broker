"""Sink connector: write to the outside first, commit the offset second.

A sink connector is the mirror of a source: it consumes records
from the broker and writes them to an external system, a database,
a search index, an object store, and its correctness hinges on the
same ordering the outbox and the consumer commit hinge on, applied
the other way. The record is delivered to the external system
first, and only once that write is confirmed does the connector
commit the Kafka offset for it, because committing the offset first
would, after a crash, resume past a record whose external write
never happened, losing it from the sink. So the connector holds the
offsets of records written to the external system but not yet
confirmed, and commits an offset only up to the confirmed prefix,
which may lag the consumed position while writes are in flight. This
gives at-least-once into the sink: a crash re-consumes records
whose external write happened but whose offset was not yet
committed, so the sink sees them twice, which is why a sink
connector either writes idempotently, keyed so a repeat overwrites
rather than duplicates, or deduplicates on its own side. The
connector consumes records, marks them confirmed as the external
system acknowledges, and commits the contiguous confirmed prefix,
refusing to commit past an unconfirmed record, the gap that would
lose it from the sink. It refuses to confirm a record it never
consumed, a bookkeeping error, and reports the committed offset
against the consumed position, because a committed offset far
behind the consumed one is a sink slow to acknowledge writes, a
backlog that grows the re-delivery on a crash and the duplicates
the sink must absorb."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class SinkConnector:
    inflight: dict[int, bool] = field(default_factory=dict)
    committed: int = -1
    consumed: int = -1

    def consume(self, offset: int) -> None:
        if offset <= self.consumed:
            raise Invalid(
                f"offset {offset} does not advance past the consumed "
                f"{self.consumed}; a consumer reads forward"
            )
        self.inflight[offset] = False
        self.consumed = offset

    def confirm_write(self, offset: int) -> None:
        if offset not in self.inflight:
            raise Invalid(f"offset {offset} was never consumed to be confirmed")
        self.inflight[offset] = True

    def commit(self) -> int:
        for offset in sorted(self.inflight):
            if self.inflight[offset]:
                self.committed = offset
                del self.inflight[offset]
            else:
                break
        return self.committed

    def report(self) -> str:
        behind = self.consumed - self.committed
        return (
            f"committed offset {self.committed}, consumed {self.consumed}, "
            f"{behind} written but not yet committable; a large gap is a sink "
            "slow to acknowledge, growing the re-delivery and duplicates on a "
            "crash"
        )
