"""Linger: waiting a little to batch a lot, and the curve that isn't obvious.

A producer can send each record the instant it is ready, or wait
a short linger time to let more records accumulate into one
batch, and the tradeoff feels like it should be linear, more
linger equals more latency equals bigger batches. It is not
linear, and the nonlinearity is the whole reason to tune it. At
zero linger a producer at high record rate still batches, because
records arriving while the previous send is in flight naturally
group, so the first few milliseconds of linger add almost no
latency while substantially growing batches by catching records
that would have just missed each other. Past a point the batch is
already as full as the record rate can fill it, and further
linger is pure latency for no batching gain, records waiting on a
timer that has nothing left to collect. The model computes batch
size as a function of linger given a record arrival rate, and the
optimal linger is where the marginal batching gain per unit
latency falls below a threshold, the knee of the curve, not the
maximum and not zero. The report states the knee and warns
against the two wrong intuitions: zero linger leaves free
batching on the table at high rates, and large linger buys
latency that the record rate cannot convert into batches, and a
producer set to either extreme is mistuned in a way that a linear
mental model cannot see.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class LingerModel:
    records_per_tick: float
    max_batch: int

    def __post_init__(self) -> None:
        if self.records_per_tick <= 0 or self.max_batch < 1:
            raise Invalid(
                "record rate and batch size must be positive"
            )

    def batch_size_at(self, linger: int) -> int:
        if linger < 0:
            raise Invalid("linger cannot be negative")
        collected = int(self.records_per_tick * linger) + 1
        return min(collected, self.max_batch)

    def marginal_gain(self, linger: int) -> int:
        return self.batch_size_at(linger + 1) - self.batch_size_at(
            linger
        )

    def optimal_linger(self, max_linger: int) -> int:
        best = 0
        for linger in range(max_linger + 1):
            if self.batch_size_at(linger) >= self.max_batch:
                return linger
            if self.marginal_gain(linger) >= 1:
                best = linger + 1
        return best

    def report(self, max_linger: int) -> str:
        knee = self.optimal_linger(max_linger)
        at_zero = self.batch_size_at(0)
        at_knee = self.batch_size_at(knee)
        return (
            f"knee at linger {knee}: batch grows {at_zero} -> "
            f"{at_knee}; zero linger leaves free batching on the "
            "table at high rates, and large linger buys latency "
            "the record rate cannot convert into batches"
        )
