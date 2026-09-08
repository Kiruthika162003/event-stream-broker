"""A retention day: rolling, compacting, expiring, and an explicit trim.

Run with: python -m examples.retentionday
"""

from __future__ import annotations

from relay.compaction import Compactor, KeyedEntry
from relay.deleterecords import LogHead
from relay.deleteretention import DeleteRetention, Tombstone
from relay.timeroll import TimeRollPolicy


def morning_the_time_roll():
    policy = TimeRollPolicy(max_bytes=1000, max_open_ticks=100)
    verdict = policy.should_roll(
        segment_bytes=50, opened_at=0, now=200, has_records=True
    )
    print(f"morning: {verdict.split(',')[0]}")


def midday_the_compaction():
    entries = [
        KeyedEntry(0, b"user-1", b"addr-a"),
        KeyedEntry(1, b"user-2", b"addr-x"),
        KeyedEntry(2, b"user-1", b"addr-b"),
        KeyedEntry(3, b"user-1", b"addr-c"),
    ]
    compactor = Compactor(tombstone_retention_ticks=100)
    compactor.compact(
        entries, now=0, tombstone_ticks={}, min_consumer_offset=0
    )
    print(f"midday:  {compactor.report(original_count=4)}")


def afternoon_the_tombstone():
    retention = DeleteRetention(retention_ticks=1000)
    tombstone = Tombstone(key=b"user-9", offset=500, eligible_at=100)
    verdict = retention.explain(
        tombstone, now=200, min_consumer_offset=600
    )
    print(f"afternoon: {verdict}")


def evening_the_trim():
    head = LogHead(log_start=100, high_watermark=1000)
    verdict = head.delete_before(
        500, committed_offsets={"billing": 800}
    )
    print(f"evening: {verdict}")


def main() -> int:
    morning_the_time_roll()
    midday_the_compaction()
    afternoon_the_tombstone()
    evening_the_trim()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
