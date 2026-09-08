"""Reservoir sample: keep a uniform sample of a stream you cannot buffer.

Sampling records for tracing or debugging wants a uniform random
sample, each record equally likely to be picked, but a stream's
length is not known in advance and buffering it all to sample at
the end is the memory the sampling was meant to avoid. Reservoir
sampling solves it in one pass with a fixed reservoir of the sample
size: the first k records fill the reservoir, and each later record,
the i-th, replaces a random reservoir slot with probability k over
i, which is exactly the probability that keeps every record seen so
far equally likely to be in the reservoir. The proof is the
invariant: after seeing i records, each has probability k over i of
being in the reservoir, and admitting the next with probability k
over i plus one, while shrinking the others' by the same factor,
preserves it, so at the end every one of n records has probability
k over n, a uniform sample without ever holding more than k. This
is why reservoir sampling is the tool for a stream: the reservoir
is fixed memory regardless of how long the stream runs, and the
sample is unbiased at every point, so it is valid even if the
stream is cut off early. The sampler fills the reservoir, then for
each later item rolls the replacement and swaps if it hits, taking
the roll from an injected source so the sampling is deterministic
under test. It refuses a reservoir size below one, which samples
nothing, and reports how many items it has seen against the
reservoir size, because a reservoir not yet full is a stream
shorter than the sample size, where the sample is the whole stream
and no sampling has happened yet.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class Reservoir:
    size: int
    reservoir: list[int] = field(default_factory=list)
    seen: int = 0

    def __post_init__(self) -> None:
        if self.size < 1:
            raise Invalid("a reservoir samples at least one item")

    def offer(self, item: int, roll: Callable[[int], int] | None = None) -> None:
        self.seen += 1
        if len(self.reservoir) < self.size:
            self.reservoir.append(item)
            return
        # replace slot with probability size/seen: pick j in [0, seen);
        # if j < size, it lands in the reservoir at slot j
        picker = roll or (lambda n: n)  # default keeps (no replacement)
        j = picker(self.seen)
        if 0 <= j < self.size:
            self.reservoir[j] = item

    def sample(self) -> list[int]:
        return list(self.reservoir)

    def fill_note(self) -> str:
        if len(self.reservoir) < self.size:
            return (
                f"{len(self.reservoir)}/{self.size} filled; the stream is "
                "shorter than the sample, so the sample is the whole stream "
                "and no sampling has happened yet"
            )
        return f"full at {self.size}; each of {self.seen} seen has equal odds"
