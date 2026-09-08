"""Split vote: nobody won, so stagger the retries instead of colliding again.

An election can end with no winner: if several candidates start at
once and the votes split among them, none reaches a majority, the
term ends leaderless, and a new election must be held. The trap is
holding that new election the same way, with every candidate timing
out and campaigning at the same moment again, because that just
reproduces the split, and a cluster can livelock through term after
term electing no one. The fix is randomized election timeouts: each
node waits a random time within a range before starting a
candidacy, so the timeouts spread out, one node almost always times
out clearly before the others, campaigns alone, and collects a
majority before anyone else starts, ending the split. The range
matters: too narrow and the randomization does not separate the
timeouts enough to avoid a re-split, too wide and the cluster waits
needlessly long after a real leader failure, so the range is tuned a
few multiples of the round-trip time, wide enough to separate,
narrow enough to fail over fast. The model detects a split, no
candidate with a majority, and computes staggered timeouts from a
base plus a random offset per node, so the earliest-timing node
campaigns first. It refuses a randomization range of zero, which
gives every node the same timeout and guarantees a re-split, and it
reports whether a vote tally is a win or a split, and for a split
which node will wake first, because a cluster that keeps splitting
is one whose timeout range is too narrow for its node count, a
tuning problem the repeated splits diagnose."
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class SplitVote:
    voters: int
    base_timeout: int
    jitter_range: int

    def __post_init__(self) -> None:
        if self.jitter_range < 1:
            raise Invalid(
                "a zero randomization range gives every node the same timeout "
                "and guarantees a re-split"
            )

    def majority(self) -> int:
        return self.voters // 2 + 1

    def is_split(self, tally: dict[str, int]) -> bool:
        return not any(v >= self.majority() for v in tally.values())

    def staggered_timeouts(
        self, nodes: list[str], roll: Callable[[str], int]
    ) -> dict[str, int]:
        return {n: self.base_timeout + (roll(n) % self.jitter_range) for n in nodes}

    def first_to_wake(
        self, nodes: list[str], roll: Callable[[str], int]
    ) -> str:
        timeouts = self.staggered_timeouts(nodes, roll)
        return min(timeouts, key=timeouts.get)

    def report(self, tally: dict[str, int]) -> str:
        if not self.is_split(tally):
            winner = max(tally, key=tally.get)
            return f"'{winner}' won with {tally[winner]}/{self.voters}"
        return (
            f"split vote, no majority of {self.majority()}; randomized "
            "timeouts stagger the retry so one node campaigns alone, and a "
            "cluster that keeps splitting has too narrow a timeout range"
        )
