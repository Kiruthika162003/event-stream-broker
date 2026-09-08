"""The partition: an ordered log with a line consumers may not cross.

A partition wraps one segment log and adds the broker's most
consequential number, the high watermark: the offset up to
which records are considered committed, replicated durably
enough to survive the leader's death. Producers append past
the watermark freely; consumers read only below it, because
serving an unreplicated record is a promise the broker cannot
keep if the leader dies in the next tick, and a consumer that
processed a record which then un-happened is the worst bug in
streaming, the one that looks like the consumer's fault. The
watermark only advances, never retreats, and advancing it past
the log's end is refused as a bookkeeping lie; the gap between
end and watermark is the partition's honesty interval, records
that exist but are not yet promises.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid, Missing
from relay.records import Record
from relay.segmentlog import SegmentLog


@dataclass
class Partition:
    number: int
    log: SegmentLog = field(default_factory=SegmentLog)
    high_watermark: int = 0

    def append(self, record: Record) -> int:
        return self.log.append(record)

    def advance_watermark(self, to_offset: int) -> str:
        if to_offset < self.high_watermark:
            raise Invalid(
                f"the watermark only advances: {to_offset} is "
                f"behind {self.high_watermark}, and a retreating "
                "watermark un-promises delivered records"
            )
        if to_offset > self.log.next_offset():
            raise Invalid(
                f"cannot commit through {to_offset}: the log "
                f"ends at {self.log.next_offset() - 1}, and a "
                "watermark past the end is a bookkeeping lie"
            )
        self.high_watermark = to_offset
        return (
            f"partition {self.number} committed through "
            f"{to_offset - 1}"
        )

    def consume(self, offset: int) -> Record:
        if offset >= self.high_watermark:
            raise Missing(
                f"offset {offset} is not yet committed "
                f"(watermark {self.high_watermark}); an "
                "unreplicated record served now could "
                "un-happen, and that bug wears the consumer's "
                "name"
            )
        return self.log.read(offset)

    def honesty_interval(self) -> str:
        uncommitted = (
            self.log.next_offset() - self.high_watermark
        )
        return (
            f"partition {self.number}: {uncommitted} record(s) "
            "exist but are not yet promises"
        )

    def lag_of(self, committed_offset: int) -> int:
        if committed_offset > self.high_watermark:
            raise Invalid(
                "a consumer cannot be ahead of the watermark"
            )
        return self.high_watermark - committed_offset
