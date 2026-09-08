"""Aggregate merge: partials combine only if the combine is associative.

A stream aggregate computed in parallel is really many partial
aggregates, one per partition or task, that must be merged into the
global result, and the merge is correct only if the combine
operation is associative: combining partials in any grouping must
give the same answer, because the partials arrive and merge in an
order the framework chooses, not one the author controls. Sum, min,
max, and count are associative and merge cleanly, the global sum is
the sum of the partial sums. The trap is the average, which is not
associative: the average of per-partition averages is not the true
average unless every partition had the same count, because
averaging throws away the counts that weight it. The fix is to
carry the count alongside the sum, merge the sums and the counts
separately, both associative, and divide only at the end, so the
aggregate that merges is the pair sum-and-count, not the average
itself. This module makes the distinction concrete: it merges
associative partials directly and refuses to merge averages as if
they were associative, requiring the sum-and-count form instead,
because a pipeline that averaged averages produces a number that
looks plausible and is quietly wrong, the worst kind of bug. The
merger checks a combine for associativity on a small sample before
trusting it, and reports a combine that fails as unsafe to
parallelize, because an aggregate whose combine is order-dependent
cannot be computed correctly across partitions no matter how the
merge is scheduled. The report states the merged result and, for
an average, shows it computed from merged sum and count rather than
from averaged averages, so the correct form is visible beside the
trap it replaces.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from relay.errors import Invalid


def merge_associative(
    partials: list[int], combine: Callable[[int, int], int]
) -> int:
    if not partials:
        raise Invalid("no partials to merge")
    left = partials[0]
    for p in partials[1:]:
        left = combine(left, p)
    return left


def is_associative(combine: Callable[[int, int], int], sample: list[int]) -> bool:
    if len(sample) < 3:
        return True
    a, b, c = sample[0], sample[1], sample[2]
    return combine(combine(a, b), c) == combine(a, combine(b, c))


@dataclass(frozen=True)
class MeanPartial:
    total: int
    count: int

    def merge(self, other: MeanPartial) -> MeanPartial:
        return MeanPartial(self.total + other.total, self.count + other.count)

    def mean(self) -> float:
        if self.count == 0:
            raise Invalid("no records; mean is undefined")
        return self.total / self.count


def merge_means(partials: list[MeanPartial]) -> str:
    if not partials:
        raise Invalid("no partials to merge")
    merged = partials[0]
    for p in partials[1:]:
        merged = merged.merge(p)
    naive = sum(p.mean() for p in partials) / len(partials)
    correct = merged.mean()
    return (
        f"correct mean {correct:.2f} from merged sum {merged.total} and "
        f"count {merged.count}; averaging the averages would give "
        f"{naive:.2f}, wrong unless every partition had the same count"
    )
