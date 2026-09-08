"""Bulkhead: separate pools so one slow operation cannot sink the whole broker.

A ship survives a hull breach because bulkheads keep the flooding
to one compartment, and a broker applies the same idea to its
resources: instead of one shared pool of request-handler threads
that every operation draws from, it partitions the threads into
pools per operation class, so a flood of one class cannot consume
the threads another class needs. Without bulkheads, a burst of slow
fetches, each holding a thread while it waits on a slow disk, ties
up every handler thread, and produces and heartbeats that would
have been fast are stuck behind them with no thread to run on, so
one slow operation class takes the whole broker down. With
bulkheads, the slow fetches fill only the fetch pool and are
rejected once it is full, while the produce and heartbeat pools
keep their threads and keep serving, so the damage is contained to
the class that caused it. The tradeoff is utilization: partitioned
pools cannot lend threads across classes, so a class can be
rejecting requests while another class's pool sits idle, capacity
that a shared pool would have used, and the pool sizes must be set
from each class's real demand or a mis-sized pool rejects work
there was capacity for elsewhere. The bulkhead admits a request to
its class's pool while the pool has room and rejects it when full,
naming that the rejection is contained rather than a broker-wide
failure, and it refuses a zero-size pool, which admits nothing. It
reports each pool's utilization, because a pool consistently full
while others idle is a partition set wrong for the real demand, the
utilization cost of isolation to tune against."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class Bulkhead:
    pool_sizes: dict[str, int]
    in_use: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if any(size < 1 for size in self.pool_sizes.values()):
            raise Invalid("every pool must have positive size")
        self.in_use = dict.fromkeys(self.pool_sizes, 0)

    def acquire(self, cls: str) -> str:
        if cls not in self.pool_sizes:
            raise Invalid(f"no pool for operation class '{cls}'")
        if self.in_use[cls] >= self.pool_sizes[cls]:
            raise Invalid(
                f"the '{cls}' pool is full ({self.pool_sizes[cls]}); rejecting "
                "here, contained to this class, other pools keep serving"
            )
        self.in_use[cls] += 1
        return f"acquired a '{cls}' thread, {self.in_use[cls]}/{self.pool_sizes[cls]}"

    def release(self, cls: str) -> None:
        if self.in_use.get(cls, 0) > 0:
            self.in_use[cls] -= 1

    def utilization(self) -> str:
        parts = [
            f"{cls} {self.in_use[cls]}/{size}"
            for cls, size in self.pool_sizes.items()
        ]
        return (
            "; ".join(parts)
            + "; a pool full while others idle is a partition set wrong for "
            "the demand, the utilization cost of isolation"
        )
