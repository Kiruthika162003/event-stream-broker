"""HyperLogLog: count distinct items in tiny memory by watching for rare runs.

Counting how many distinct keys or distinct clients a stream has
seen would seem to need a set of everything seen, memory that grows
with the count. HyperLogLog estimates the distinct count in a fixed
few kilobytes no matter how many distinct items pass, using a
probabilistic idea: in a stream of random hashes, seeing a hash
with many leading zeros is rare, and the more distinct items you
hash the more likely you are to have seen a long run of leading
zeros, so the longest run observed is evidence of how many distinct
items there were. One run is noisy, so the hash is split: a few
bits pick one of many registers and the rest supply the run, each
register keeps the longest run it saw, and the estimate combines
the registers so the noise of any one averages out. The combination
is a harmonic mean across the registers scaled by a constant, which
turns the per-register run lengths into a cardinality estimate whose
error shrinks as the register count grows, trading a little more
memory for a tighter estimate. The estimator adds items by updating
the register their hash selects, and estimates by combining the
registers, and it reports that the count is approximate with an
error bound from the register count, because treating an HLL
estimate as exact is the mistake, it is right to within a few
percent and wrong to the exact unit. It refuses a register count
that is not a positive power of two, because the register-selecting
bits index a power-of-two table and a non-power-of-two would waste
or overflow it. Adding the same item twice does not change the
estimate, the property that makes it count distinct items rather
than total items, which the tests check directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


def _leading_zeros(value: int, width: int) -> int:
    for i in range(width):
        if value & (1 << (width - 1 - i)):
            return i
    return width


@dataclass
class HyperLogLog:
    registers: int = 16
    _regs: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.registers < 1 or (self.registers & (self.registers - 1)) != 0:
            raise Invalid("register count must be a positive power of two")
        if not self._regs:
            self._regs = [0] * self.registers

    def add(self, item: str) -> None:
        h = hash(item) & 0xFFFFFFFF
        bucket_bits = self.registers.bit_length() - 1
        bucket = h & (self.registers - 1)
        rest = h >> bucket_bits
        run = _leading_zeros(rest, 32 - bucket_bits) + 1
        self._regs[bucket] = max(self._regs[bucket], run)

    def estimate(self) -> int:
        m = self.registers
        alpha = 0.7213 / (1 + 1.079 / m)
        denom = sum(2.0 ** -r for r in self._regs)
        raw = alpha * m * m / denom
        return int(raw)

    def error_bound(self) -> str:
        rel = 1.04 / (self.registers ** 0.5)
        return (
            f"~{rel * 100:.1f}% relative error from {self.registers} "
            "registers; the estimate is approximate, right to a few percent, "
            "not exact to the unit"
        )
