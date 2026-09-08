"""A streams day: extract event time, advance the watermark, window, suppress.

Run with: python -m examples.streamsday
"""

from __future__ import annotations

from relay.eventtime import USE_ARRIVAL, EventTimeExtractor
from relay.suppression import Suppressor
from relay.tablestreamduality import TableStream
from relay.watermarkgen import WatermarkGenerator


def morning_event_time():
    extractor = EventTimeExtractor(field_name="ts", fallback=USE_ARRIVAL)
    got = extractor.extract({"ts": 1000}, arrival_time=9999)
    missing = extractor.extract({}, arrival_time=9999)
    print(f"morning: extracted {got}, missing fell back to {missing}")


def midmorning_watermark():
    gen = WatermarkGenerator(lateness_bound=5)
    gen.observe(100)
    gen.observe(120)
    late = gen.is_late(90)
    print(f"         watermark at {gen.watermark}; a record at 90 is late: {late}")


def noon_fold_a_table():
    ts = TableStream()
    for value in (1, 5, 3):
        ts.fold("cust1", value)
    ts.fold("cust1", None)  # tombstone deletes
    ts.fold("cust2", 9)
    print(f"noon:    table now {ts.table}; {ts.compaction_ratio()}")


def afternoon_suppress_until_final():
    s = Suppressor(grace=10)
    s.update(window_end=100, value=1)
    s.update(window_end=100, value=2)
    s.update(window_end=100, value=3)
    early = s.advance(stream_time=105)
    final = s.advance(stream_time=115)
    print(f"afternoon: early emit {early}, final emit {final}; {s.savings()}")


def main() -> int:
    morning_event_time()
    midmorning_watermark()
    noon_fold_a_table()
    afternoon_suppress_until_final()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
