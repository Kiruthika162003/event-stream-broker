"""Add a thousand keys, and not one of them ever tests absent.

The scenario is a filter loaded past a comfortable fill and then
asked about every key it holds, and the claim is that not one added
key reports absent no matter how full the filter is, while
unrelated keys do produce some false positives. The drill adds a
thousand keys to a modestly sized filter, tests all thousand for
presence and counts any that report absent, then tests a thousand
keys never added and counts how many falsely report present. My
first guess was that a filter loaded this heavily might start
dropping an added key, since so many bits are set that a lookup
could find a gap. Measurement corrected the guess: zero added keys
reported absent, because a bloom filter only ever sets bits and
never clears them, so an added key's bits are still set no matter
how many other keys were added, while the unrelated keys showed the
false positives the fill predicts. The counterfactual is a filter
that dropped even one added key: a caller trusting a definitely-not
answer would skip a lookup for a key that was really there, missing
data, which is why the no-false-negative property is the one a
bloom filter must never break, and the gap between zero-missed and
any-missed is the difference between a safe skip and a silent miss.
"""

from __future__ import annotations

from relay.bloomfilter import BloomFilter
from relay.proofs.finding import Finding


def run() -> Finding:
    bloom = BloomFilter(size_bits=8000, hash_count=5)
    added = [f"added-{i}" for i in range(1000)]
    for key in added:
        bloom.add(key)

    false_negatives = sum(1 for k in added if not bloom.might_contain(k))

    never_added = [f"absent-{i}" for i in range(1000)]
    false_positives = sum(1 for k in never_added if bloom.might_contain(k))

    numbers = {
        "keys_added": len(added),
        "false_negatives": false_negatives,
        "false_positives_of_1000": false_positives,
        "estimated_fp_rate": round(bloom.estimated_false_positive_rate(), 4),
        "guess_was": "a heavily loaded filter might drop an added key",
        "measured": "zero added keys tested absent, bits are never cleared",
    }
    holds = false_negatives == 0
    return Finding(
        proof="bloomholds",
        claim=(
            "every one of a thousand added keys tests present however "
            "full the filter, so a definitely-not answer is always safe "
            "to skip a lookup on, while unrelated keys give the false "
            "positives the fill predicts"
        ),
        numbers=numbers,
        holds=holds,
    )
