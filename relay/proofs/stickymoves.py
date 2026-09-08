"""A member joins a large group, and sticky moves a fraction of what naive does.

The scenario is the one that decides whether a production group
with warm local state survives a routine scale-up: a group of
nine members owning ninety partitions, and a tenth member joins.
Naive assignment re-slices from scratch and reshuffles most of
the ninety, each moved partition paying a revoke, a state flush,
and a cold re-fetch. Sticky assignment moves only the partitions
that must move to bring the newcomer to its fair share. The drill
runs both on the same before-and-after and counts moves. The
guess before measuring was that sticky would move about a tenth,
one member's worth; the measurement is that it moves exactly the
newcomer's fair share and not one partition more, while naive
moves several times that, and the ratio between them is the
factor by which sticky reduces rebalance pain. The number that
matters is not either count alone but their gap, because that gap
is the count of partitions that needlessly flushed state and
re-fetched under naive, work that bought nothing, and a group
that felt every one of those moves as a stall is the reason the
sticky assignor exists.
"""

from __future__ import annotations

from relay.proofs.finding import Finding
from relay.rebalance import naive_moved, sticky_assign

PARTITIONS = list(range(90))


def run() -> Finding:
    nine = [f"c{n}" for n in range(9)]
    ten = [f"c{n}" for n in range(10)]
    before, _ = sticky_assign(PARTITIONS, nine)
    _, sticky = sticky_assign(PARTITIONS, ten, previous=before)
    naive = naive_moved(PARTITIONS, ten, before)
    fair_share = len(PARTITIONS) // len(ten)
    numbers = {
        "partitions": len(PARTITIONS),
        "sticky_moves": sticky,
        "naive_moves": naive,
        "newcomer_fair_share": fair_share,
        "wasted_by_naive": naive - sticky,
        "sticky_is_fair_share": sticky == fair_share,
    }
    holds = (
        sticky == fair_share
        and naive > sticky * 2
        and numbers["wasted_by_naive"] > 0
    )
    return Finding(
        proof="stickymoves",
        claim=(
            "a member joining a group of ninety partitions moves "
            "exactly the newcomer's fair share under sticky and "
            "several times that under naive; the gap is the "
            "partitions that needlessly flushed state for nothing"
        ),
        numbers=numbers,
        holds=holds,
    )
