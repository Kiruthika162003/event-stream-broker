"""Change the voter set by one and no two majorities miss each other; by two, they can.

The scenario is a membership change during which the cluster
briefly holds two voter sets, the old and the new, and the claim is
that a single-voter change keeps every old majority overlapping
every new majority, so two leaders cannot be elected, while a
two-voter change breaks that. The drill enumerates, for a change of
one voter from a three-set to a four-set, every majority-sized
subset of each and checks that all cross pairs share a node, then
does the same for a two-voter jump from three to five and looks for
a disjoint pair. My first guess was that a majority of each set
would always overlap simply because both are more than half of
something, but the halves are of different-sized sets, so that
reasoning does not hold across a big jump. Measurement showed the
split: the single-voter change had zero disjoint majority pairs
across every combination, while the two-voter jump did have a
disjoint pair, two old nodes and three new nodes with no member in
common, exactly the two-leader hazard. The counterfactual is a
cluster that changed by two in one step: it could elect two leaders
during the change, the split brain a quorum exists to prevent, and
the gap between zero disjoint pairs at one voter and a real one at
two is why membership changes go one voter at a time.
"""

from __future__ import annotations

from itertools import combinations

from relay.proofs.finding import Finding


def _majorities(members: set[str]) -> list[frozenset[str]]:
    size = len(members) // 2 + 1
    return [frozenset(c) for c in combinations(sorted(members), size)]


def _disjoint_pairs(a: set[str], b: set[str]) -> int:
    count = 0
    for ma in _majorities(a):
        for mb in _majorities(b):
            if not (ma & mb):
                count += 1
    return count


def run() -> Finding:
    old = {"n1", "n2", "n3"}
    one_voter = {"n1", "n2", "n3", "n4"}
    two_voter = {"n1", "n2", "n3", "n4", "n5"}

    single_disjoint = _disjoint_pairs(old, one_voter)
    double_disjoint = _disjoint_pairs(old, two_voter)

    numbers = {
        "single_voter_disjoint_majority_pairs": single_disjoint,
        "two_voter_disjoint_majority_pairs": double_disjoint,
        "guess_was": "a majority of each always overlaps",
        "measured": "true at one voter, false at two",
    }
    holds = single_disjoint == 0 and double_disjoint > 0
    return Finding(
        proof="nosplitbrain",
        claim=(
            "a single-voter membership change leaves no two disjoint "
            "majorities so no split brain, while a two-voter jump admits "
            "one, which is why membership changes go one voter at a time"
        ),
        numbers=numbers,
        holds=holds,
    )
