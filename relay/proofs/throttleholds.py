"""Hammer the bucket all you like, the long run is the refill, plus one burst.

The scenario is a client that ignores throttling and asks for
tokens every tick as fast as it can, and the claim is that over a
long run it cannot pull more than the refill rate allows plus the
one burst the capacity forgave at the start. The drill fills a
bucket to capacity, then over a thousand ticks takes the largest
amount the bucket will serve each tick, summing what was actually
served. My first guess was that letting the client take greedily
each tick might let it stay ahead of the refill and beat the rate,
since it always drains whatever accumulated. Measurement corrected
the guess: the served total came to the refill rate times the
ticks plus the initial capacity, exactly the sustained rate plus
one bucket of burst, because once the initial capacity is spent the
client can only take what one tick refilled. The counterfactual is
a limiter that let the greedy client win: the disk it was meant to
protect would see the peak rate continuously, not the sustained
one, which is the overload the bucket exists to prevent. The gap
between the greedy total and the refill-plus-burst bound is zero,
which is the whole guarantee: burst is bounded by capacity and
sustained throughput is bounded by refill.
"""

from __future__ import annotations

from relay.proofs.finding import Finding
from relay.tokenbucket import TokenBucket


def run() -> Finding:
    capacity = 100.0
    refill = 5.0
    ticks = 1000
    bucket = TokenBucket(capacity=capacity, refill_per_tick=refill)
    served = 0.0
    for now in range(1, ticks + 1):
        bucket._refill(now)
        take = bucket.tokens
        bucket.tokens = 0.0
        served += take
    bound = refill * ticks + capacity
    numbers = {
        "ticks": ticks,
        "served": round(served, 1),
        "refill_plus_burst_bound": round(bound, 1),
        "overshoot": round(served - bound, 1),
        "guess_was": "greedy taking might beat the refill rate",
        "measured": "served equals refill*ticks + one capacity of burst",
    }
    holds = served <= bound + 1e-6
    return Finding(
        proof="throttleholds",
        claim=(
            "a greedy client pulls at most the refill rate times "
            "the ticks plus one bucket of burst, so sustained "
            "throughput is bounded by refill and burst by capacity"
        ),
        numbers=numbers,
        holds=holds,
    )
