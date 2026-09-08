"""Fetch coalesce: overlapping read ranges become one, so the disk is read once.

A fetch request can name many partitions, and within the broker's
read path several requested ranges on the same segment can overlap
or sit right next to each other, because different consumers of the
same partition ask for nearby offsets at nearly the same time. If
each range is read from disk separately the segment's bytes are
read more than once, so the read path first coalesces the ranges:
it sorts them by start offset and merges any range that overlaps or
abuts the one before it into a single wider range, turning many
small reads into a few large ones. Abutting matters as much as
overlapping: two ranges where one ends exactly where the next
begins have no gap between them, so reading them as one contiguous
span costs nothing extra and saves a second seek, which on a
spinning disk is the expensive part. The merge is only valid on
sorted input, so the coalescer sorts first, because merging
unsorted ranges would miss a pair that overlaps but arrives out of
order. The coalescer refuses a range whose end is not past its
start, because an empty or backwards range is a caller bug that
would otherwise merge into and corrupt a valid neighbor. The report
states the read amplification avoided, the difference between the
byte span the raw ranges would have read counting overlaps twice
and the span the coalesced ranges read once, because a read path
whose ranges never overlap gains nothing from coalescing and one
whose ranges overlap heavily gains the most.
"""

from __future__ import annotations

from relay.errors import Invalid


def coalesce(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    for start, end in ranges:
        if end <= start:
            raise Invalid(
                f"range ({start}, {end}) is empty or backwards; a "
                "caller bug that would corrupt a valid neighbor if "
                "merged"
            )
    if not ranges:
        return []
    ordered = sorted(ranges)
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def amplification(ranges: list[tuple[int, int]]) -> str:
    raw = sum(end - start for start, end in ranges)
    coalesced = sum(end - start for start, end in coalesce(ranges))
    saved = raw - coalesced
    return (
        f"{len(ranges)} range(s) reading {raw} byte(s) raw coalesce "
        f"to {len(coalesce(ranges))} reading {coalesced}; {saved} "
        "byte(s) of duplicate reading avoided, the win growing with "
        "how much the ranges overlap"
    )
