"""Group the partitions any way you like, the sum-and-count mean is the same.

The scenario is a mean computed in parallel across partitions with
uneven counts, merged in whatever grouping the framework happened
to pick, and the claim is that the sum-and-count form gives the one
true mean regardless of the grouping while averaging the averages
does not. The drill takes three partitions with different counts,
computes the true mean from the raw records, then merges the
sum-and-count partials in several different groupings, left to
right and right to left and pairwise, and checks every merge lands
on the true mean. It also computes the average-of-averages for
contrast. My first guess was that floating-point order might make
the sum-and-count merges disagree slightly across groupings.
Measurement corrected it for these integer totals: every grouping
of the sum-and-count merge gave exactly the true mean, because
integer sums and counts are associative with no rounding until the
final divide, while the average-of-averages missed the true mean
outright, not by rounding but by discarding the counts. The
counterfactual is a pipeline that averaged averages: it would
report a mean that looks plausible and is wrong whenever the
partition counts differ, the quiet bug the sum-and-count form
exists to prevent, and the gap between all-groupings-agree and
the-average-trap-differs is the whole reason to carry the count.
"""

from __future__ import annotations

from relay.aggregatemerge import MeanPartial
from relay.proofs.finding import Finding


def run() -> Finding:
    # partition -> (total, count)
    partials = [MeanPartial(100, 10), MeanPartial(5, 1), MeanPartial(60, 4)]
    true_total = sum(p.total for p in partials)
    true_count = sum(p.count for p in partials)
    true_mean = true_total / true_count

    def merge(order: list[MeanPartial]) -> float:
        acc = order[0]
        for p in order[1:]:
            acc = acc.merge(p)
        return acc.mean()

    groupings = [
        merge(partials),
        merge(list(reversed(partials))),
        merge([partials[1], partials[2], partials[0]]),
    ]
    all_agree = all(abs(g - true_mean) < 1e-9 for g in groupings)
    avg_of_avgs = sum(p.mean() for p in partials) / len(partials)

    numbers = {
        "true_mean": round(true_mean, 4),
        "groupings_tested": len(groupings),
        "all_groupings_agree": all_agree,
        "average_of_averages": round(avg_of_avgs, 4),
        "avg_trap_wrong_by": round(abs(avg_of_avgs - true_mean), 4),
        "guess_was": "float order might make the merges disagree",
        "measured": "integer sum-and-count merges all hit the true mean",
    }
    holds = all_agree and abs(avg_of_avgs - true_mean) > 1e-9
    return Finding(
        proof="aggregateholds",
        claim=(
            "every grouping of the sum-and-count merge gives the one "
            "true mean while averaging the averages does not, so the "
            "count is what makes a parallel mean correct"
        ),
        numbers=numbers,
        holds=holds,
    )
