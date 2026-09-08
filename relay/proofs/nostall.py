"""Adding a consumer, and the partitions that stay put never pause.

Cooperative rebalancing's whole claim is that unmoved partitions
keep serving while the moving ones change hands, and this proof
drives the exact scenario and counts. A group of two consumers
holds eight partitions, four each; a third consumer joins,
rebalancing to a target of roughly three each. The drill runs
the two-phase cooperative protocol and measures three numbers
against the stop-the-world alternative: how many partitions were
revoked, how many kept serving throughout, and whether any
partition was ever owned by two consumers across the phases. The
guess before measuring was that adding a third to a group of two
would move about a third of the partitions; the measurement is
sharper, and the number that matters is the kept count, because
stop-the-world would have paused all eight while cooperative
paused only the movers. The double-ownership check is the safety
half: throughput is worthless if the protocol bought it by
letting two consumers process one partition, and the proof
confirms it never did.
"""

from __future__ import annotations

from relay.cooperative import CooperativeRebalance
from relay.proofs.finding import Finding


def run() -> Finding:
    rebalance = CooperativeRebalance(
        current={
            "c1": {0, 1, 2, 3},
            "c2": {4, 5, 6, 7},
        },
        target={
            "c1": {0, 1, 2},
            "c2": {4, 5, 6},
            "c3": {3, 7},
        },
    )
    to_revoke = rebalance.to_revoke()
    revoked_count = sum(len(v) for v in to_revoke.values())
    total = 8
    rebalance.revoke_phase()
    kept_serving = total - revoked_count
    rebalance.assign_phase()
    numbers = {
        "total_partitions": total,
        "revoked": revoked_count,
        "kept_serving": kept_serving,
        "stop_world_would_pause": total,
        "double_owned": not rebalance.never_double_owned(),
        "final_matches_target": (
            rebalance.current == rebalance.target
        ),
    }
    holds = (
        revoked_count == 2
        and kept_serving == 6
        and not numbers["double_owned"]
        and numbers["final_matches_target"]
    )
    return Finding(
        proof="nostall",
        claim=(
            "adding a third consumer moved 2 of 8 partitions and "
            "kept 6 serving throughout, where stop-the-world "
            "pauses all 8, and no partition was ever owned twice"
        ),
        numbers=numbers,
        holds=holds,
    )
