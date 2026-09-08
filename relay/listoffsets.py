"""ListOffsets: turn earliest, latest, or a timestamp into a concrete offset.

A consumer that wants to start reading from the beginning, from
the end, or from a point in time does not know the offset that
names that position, so it asks the broker to resolve a symbolic
request into a concrete offset. Earliest resolves to the log start
offset, the oldest offset still retained, which is not zero once
retention has deleted the front of the log, a distinction that
trips a consumer assuming earliest means offset zero. Latest
resolves to the high watermark, the offset one past the last
committed record, so a consumer starting at latest reads only what
arrives after it joined and sees nothing already there, which is
correct for tailing and surprising for someone who expected
history. A timestamp resolves to the offset of the earliest record
whose timestamp is at or after the target, found through the
segment time index, so a consumer can start from nine this morning
without knowing the offset that hour began at, and if no record is
that recent the answer is the high watermark, meaning start at the
end because nothing matches yet. The resolver refuses a timestamp
query against a log whose timestamps are broker-append rather than
event time, because the two clocks answer different questions and
a timestamp lookup against the wrong one silently returns a
position the consumer did not mean. The report names which
resolution was applied, because a consumer that asked for a time
and got the high watermark needs to know it got the end of the log,
not a match.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class OffsetQuery:
    log_start: int
    high_watermark: int
    timestamped: bool

    def __post_init__(self) -> None:
        if self.log_start > self.high_watermark:
            raise Invalid(
                "log start cannot be past the high watermark"
            )

    def earliest(self) -> int:
        return self.log_start

    def latest(self) -> int:
        return self.high_watermark

    def for_timestamp(
        self, target: int, records: list[tuple[int, int]]
    ) -> tuple[int, str]:
        if not self.timestamped:
            raise Invalid(
                "this log stamps records on broker append, not "
                "event time; a timestamp lookup against append "
                "time answers a different question than asked"
            )
        for offset, ts in records:
            if ts >= target:
                return offset, f"matched at offset {offset}, ts {ts}"
        return (
            self.high_watermark,
            "no record at or after the target; resolved to the "
            "high watermark, meaning start at the end because "
            "nothing matches yet, not a match at that time",
        )
