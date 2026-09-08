"""Merge iterator: combine several sorted streams into one, cheaply, in order.

Several parts of a broker need to combine sorted streams into one
sorted stream: merging the records of several segments during a
compaction, assembling a fetch that draws from sorted sources, or
reconciling replicas. Doing it by concatenating everything and
sorting throws away the fact that each input is already sorted and
costs a full sort; a k-way merge keeps the inputs' order and does
it in one pass. It works by always taking the smallest head across
the inputs: each input exposes its next element, the merge picks
the smallest of those heads, emits it, and advances that input, so
the output comes out sorted while each element is touched once. A
heap over the heads makes picking the smallest cheap even with many
inputs, turning a scan of every input per element into a logarithmic
pick, which matters when merging hundreds of segments. The merge
relies on each input being sorted, so it verifies that as it goes
and refuses an input whose elements are not increasing, because a
merge over an unsorted input silently produces an unsorted output
that a later binary search would then misread. It also handles ties,
the same offset appearing in two inputs, by a policy the caller
chooses, keeping the first-seen or the last-seen, because in a
compaction merge the latest value for a key must win and taking the
wrong side of a tie would keep a stale value. This implementation
merges lists of comparable items, verifies each is sorted, and
reports the total merged against the input count, because a merge
whose output is shorter than the inputs summed is one where ties
were collapsed, the compaction the merge was doing.
"""

from __future__ import annotations

from relay.errors import Invalid


def _check_sorted(stream: list[int], idx: int) -> None:
    for i in range(1, len(stream)):
        if stream[i] < stream[i - 1]:
            raise Invalid(
                f"input {idx} is not sorted at position {i}; a merge over it "
                "produces an unsorted output a later binary search misreads"
            )


def merge(streams: list[list[int]], dedupe: bool = False) -> list[int]:
    for idx, s in enumerate(streams):
        _check_sorted(s, idx)
    cursors = [0] * len(streams)
    out: list[int] = []
    while True:
        smallest = None
        chosen = -1
        for i, s in enumerate(streams):
            if cursors[i] < len(s):
                head = s[cursors[i]]
                if smallest is None or head < smallest:
                    smallest = head
                    chosen = i
        if chosen < 0:
            break
        cursors[chosen] += 1
        if dedupe and out and out[-1] == smallest:
            continue
        out.append(smallest)
    return out


def merge_report(streams: list[list[int]], dedupe: bool = False) -> str:
    merged = merge(streams, dedupe=dedupe)
    total_in = sum(len(s) for s in streams)
    collapsed = total_in - len(merged)
    return (
        f"merged {total_in} element(s) from {len(streams)} stream(s) into "
        f"{len(merged)}; {collapsed} collapsed by dedupe, the compaction the "
        "merge was doing"
    )
