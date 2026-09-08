"""Histogram merge: a fleet percentile comes from summed buckets, not averaged ones.

A single broker's latency percentile comes from its histogram, but
a fleet's percentile, the ninety-ninth across every broker, is a
different computation, and the tempting shortcut gets it wrong. The
shortcut is to take each broker's ninety-ninth percentile and
average them, which is wrong for the same reason averaging averages
is wrong: a percentile is not additive, and the average of
per-broker p99s is neither the fleet p99 nor any meaningful number,
because a broker with few requests contributes its p99 as heavily
as a broker with many. The right way is to merge the histograms
themselves, summing the bucket counts across brokers into one
combined histogram, and then read the percentile off the combined
counts, which weights each request equally regardless of which
broker served it. This is the histogram analogue of carrying sum
and count for a mean: the mergeable thing is the bucket counts, not
the percentile, and only after merging is the percentile taken. The
merger sums the counts of matching buckets, requires the histograms
to share the same bucket boundaries so the sums are meaningful, and
reads a percentile from the combined counts by walking the buckets
until the cumulative count crosses the target rank. It refuses to
merge histograms with mismatched bucket boundaries, because summing
counts of buckets that cover different ranges adds unrelated
numbers, and it refuses a percentile outside zero to one hundred.
It reports the fleet percentile against the naive average of the
per-broker percentiles, showing the gap, because that gap is how
wrong the shortcut would have been, larger when the brokers carry
uneven load, the case the averaging trap hides worst."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class Histogram:
    boundaries: tuple[int, ...]
    counts: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.counts) != len(self.boundaries):
            raise Invalid("counts and boundaries must have the same length")

    def percentile(self, p: float) -> int:
        if not 0 <= p <= 100:
            raise Invalid("percentile must be in [0, 100]")
        total = sum(self.counts)
        if total == 0:
            return 0
        target = p / 100 * total
        cumulative = 0
        for boundary, count in zip(self.boundaries, self.counts, strict=True):
            cumulative += count
            if cumulative >= target:
                return boundary
        return self.boundaries[-1]


def merge(histograms: list[Histogram]) -> Histogram:
    if not histograms:
        raise Invalid("no histograms to merge")
    boundaries = histograms[0].boundaries
    for h in histograms:
        if h.boundaries != boundaries:
            raise Invalid(
                "histograms have different bucket boundaries; summing counts "
                "of buckets covering different ranges adds unrelated numbers"
            )
    summed = tuple(
        sum(h.counts[i] for h in histograms) for i in range(len(boundaries))
    )
    return Histogram(boundaries=boundaries, counts=summed)


def fleet_versus_naive(histograms: list[Histogram], p: float) -> str:
    fleet = merge(histograms).percentile(p)
    naive = sum(h.percentile(p) for h in histograms) / len(histograms)
    return (
        f"fleet p{p:.0f} {fleet} from merged buckets; averaging the "
        f"per-broker p{p:.0f}s would give {naive:.0f}, off by "
        f"{abs(fleet - naive):.0f}, worse when load is uneven"
    )
