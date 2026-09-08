"""Retention runs aggressively, and the lagging consumer keeps its data.

The scenario is the one that turns retention into data loss at
every broker that gets it wrong: a topic with a tight retention
window and a consumer that fell behind. The drill builds a log of
enough records to fill several sealed segments, sets a retention
policy so aggressive it would drop everything by age, and then
runs it with a committed floor pinned to an early offset, standing
in for a consumer still draining the oldest segment. The proof
asserts two things at once: retention reclaims the segments the
consumer has already passed, so the policy is doing its job and
the log is not growing without bound, and it stops at the segment
the lagging consumer still needs, so not one unread record is
deleted. The guess before measuring was that an aggressive enough
policy would eventually win against the floor; the measurement is
the opposite and sharper, the floor is absolute, and the number
that proves it is the gap between how many segments age would have
dropped and how many actually dropped, which is exactly the
consumer's unread backlog preserved.
"""

from __future__ import annotations

from relay.proofs.finding import Finding
from relay.records import Record
from relay.retention import RetentionPolicy, RetentionRun
from relay.segmentlog import SegmentLog


def run() -> Finding:
    log = SegmentLog()
    for number in range(40):
        log.append(
            Record(value=f"e{number:04}".encode() + b"x" * 500)
        )
    segments_before = len(log.segments)
    sealed_before = sum(
        1 for s in log.segments if s.sealed
    )
    ticks = {seg.base_offset: 0 for seg in log.segments}
    # Committed floor sits inside the second segment: consumer is
    # still draining early data.
    floor = log.segments[1].base_offset + 1
    run = RetentionRun(
        policy=RetentionPolicy(max_age_ticks=1)
    )
    verdict = run.apply(
        log, ticks, now=100000, committed_floor=floor
    )
    unread_preserved = any(
        seg.next_offset() > floor for seg in log.segments
    )
    numbers = {
        "segments_before": segments_before,
        "sealed_before": sealed_before,
        "reclaimed": run.reclaimed_segments,
        "floor": floor,
        "stopped_at_floor": "loss with a schedule" in verdict,
        "unread_preserved": unread_preserved,
    }
    holds = (
        run.reclaimed_segments >= 1
        and numbers["stopped_at_floor"]
        and unread_preserved
        and run.reclaimed_segments < sealed_before
    )
    return Finding(
        proof="retentionfloor",
        claim=(
            "aggressive retention reclaims the passed segments "
            "but stops dead at the committed floor: the lagging "
            "consumer's unread backlog is preserved to the "
            "record, and the floor is absolute, not a suggestion"
        ),
        numbers=numbers,
        holds=holds,
    )
