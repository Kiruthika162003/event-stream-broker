"""A proof: a claim, the numbers that back it, and whether it holds.

The proofs in this package are not unit tests; they are
standing demonstrations that a delivery guarantee actually
holds under a scenario worth doubting. Each returns a Finding
whose docstring keeps the reasoning, including the guess that
measurement corrected, because the difference between a broker
that claims exactly-once and one that demonstrates it on a
duplicate-flood is the whole trust budget.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Finding:
    proof: str
    claim: str
    numbers: dict = field(default_factory=dict)
    holds: bool = True

    def line(self) -> str:
        mark = "holds" if self.holds else "BROKEN"
        return f"{self.proof}: {mark} -- {self.claim}"
