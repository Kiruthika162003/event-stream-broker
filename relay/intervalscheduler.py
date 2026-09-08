"""Interval scheduler: fit the most non-overlapping windows by earliest finish.

Scheduling work that must not overlap, compaction runs on a shared
disk, maintenance windows on a broker, reassignments that each
saturate the network, is the classic activity-selection problem:
given a set of intervals each with a start and an end, pick the
largest subset that do not overlap. The greedy solution is not the
obvious one. Picking the shortest interval first, or the one that
starts earliest, does not maximize the count, but picking the one
that finishes earliest does, because finishing earliest leaves the
most room for the intervals after it, and the choice is provably
optimal: sort by end time, take the first, then take each next
interval whose start is at or after the last taken one's end, and
the result is a maximum non-overlapping set. The intuition is that
the earliest-finishing interval can never be a wrong first choice,
since any schedule can be rearranged to start with it without
losing count. This is the right tool when the goal is to run as
many jobs as possible in a shared resource that admits one at a
time, rather than to run the most important, which is a different,
weighted problem. The scheduler sorts by finish time, selects the
compatible ones greedily, and reports how many of the candidates
fit. It refuses an interval whose end is not after its start, an
empty or backwards window that is a caller error rather than a
zero-length job, and reports the count selected against offered,
because a schedule fitting few of many candidates is a resource
oversubscribed, more jobs wanting the slot than the non-overlap
constraint allows, a signal to add capacity or widen the windows."
"""

from __future__ import annotations

from relay.errors import Invalid


def select(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    for start, end in intervals:
        if end <= start:
            raise Invalid(
                f"interval ({start}, {end}) ends at or before it starts; an "
                "empty or backwards window is a caller error"
            )
    chosen: list[tuple[int, int]] = []
    last_end = None
    for start, end in sorted(intervals, key=lambda iv: iv[1]):
        if last_end is None or start >= last_end:
            chosen.append((start, end))
            last_end = end
    return chosen


def schedule_report(intervals: list[tuple[int, int]]) -> str:
    if not intervals:
        return "no intervals offered; nothing to schedule"
    fit = select(intervals)
    return (
        f"{len(fit)}/{len(intervals)} interval(s) fit without overlap; fitting "
        "few of many is a resource oversubscribed, more jobs wanting the slot "
        "than the non-overlap constraint allows"
    )
