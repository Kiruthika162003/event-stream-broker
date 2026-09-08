"""Event time: the time in the record, not the time it arrived, and the fallback.

A stream that reasons about time has two clocks to choose from: the
time a record arrived at the broker, and the time the event it
describes actually happened, carried in the record itself. For
anything that must reflect when things happened, a windowed count
of events per hour, the event time is the right one, because
arrival time is distorted by network delay, batching, and replay, a
batch of an hour's events replayed now would all land in this hour
by arrival time and in their true hours by event time. So the
stream extracts event time from a field in the record, and the
extraction is where reality intrudes: a record may lack the field,
carry an unparseable value, or carry a nonsensical one, and the
stream needs a policy for each rather than crashing or silently
using a wrong time. The extractor pulls the timestamp from the
named field and, when it cannot, applies the configured fallback:
use the arrival time, drop the record, or fail the stream, each a
deliberate choice with a different cost, arrival time distorts the
windowing, dropping loses the record, failing stops the stream. It
rejects a negative or absurdly large extracted time outright rather
than passing it to windowing, because a garbage timestamp placed in
a window is worse than a missing one, it silently corrupts a window
rather than triggering the fallback. The extractor reports how many
records fell back, because a stream where most records lack a
usable event time is one extracting from the wrong field or reading
data that never had event time, a configuration error the fallback
count surfaces before the windows come out wrong.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

USE_ARRIVAL = "arrival"
DROP = "drop"
FAIL = "fail"
_MAX_REASONABLE = 10 ** 15


@dataclass
class EventTimeExtractor:
    field_name: str
    fallback: str
    fell_back: int = 0

    def __post_init__(self) -> None:
        if self.fallback not in (USE_ARRIVAL, DROP, FAIL):
            raise Invalid(f"unknown fallback policy '{self.fallback}'")

    def extract(self, record: dict, arrival_time: int) -> int | None:
        raw = record.get(self.field_name)
        if isinstance(raw, int):
            if raw < 0 or raw > _MAX_REASONABLE:
                raise Invalid(
                    f"extracted event time {raw} is negative or absurd; a "
                    "garbage timestamp in a window is worse than a missing "
                    "one, it corrupts the window silently"
                )
            return raw
        return self._fall_back(arrival_time)

    def _fall_back(self, arrival_time: int) -> int | None:
        self.fell_back += 1
        if self.fallback == USE_ARRIVAL:
            return arrival_time
        if self.fallback == DROP:
            return None
        raise Invalid(
            f"record has no usable '{self.field_name}' and the policy is "
            "fail; the stream stops rather than use a wrong time"
        )

    def fallback_note(self, total: int) -> str:
        if total == 0:
            return "no records processed"
        pct = self.fell_back / total * 100
        return (
            f"{self.fell_back}/{total} record(s) fell back ({pct:.0f}%); mostly "
            "falling back is the wrong field or data without event time, a "
            "config error before the windows come out wrong"
        )
