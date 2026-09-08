"""Cogroup: several streams fold into one shared per-key state, each its own way.

Sometimes an aggregate draws from more than one stream: a customer's
activity score might combine their orders, their support tickets,
and their logins, three separate streams that should fold into one
per-customer total. Doing this as a series of joins is awkward
because a join pairs records, while here each stream contributes
independently to a running state. Cogrouping expresses it directly:
several input streams share one keyed state, and each stream has its
own aggregator that folds its records into that state, so an order
adds its amount, a ticket subtracts a penalty, a login bumps a
counter, all into the same per-customer value. The streams must be
co-partitioned on the shared key, the same requirement as a join,
because all of one key's records from every stream must reach the
same task to fold into one state, so the cogroup refuses inputs
whose partitioning does not match. Each stream's records are folded
by that stream's aggregator, and the state for a key is the
accumulation of every contribution from every stream in arrival
order, so the result reflects all inputs rather than the last one to
write. The cogroup refuses a record from a stream it was not
configured with, an input that slipped in without an aggregator and
would have no defined effect on the state, and it reports how many
streams have contributed to a key, because a key updated by only one
of several streams is a key the other streams have not seen yet,
which for a score meant to combine all of them is an incomplete
value worth distinguishing from a complete one."
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from relay.errors import Invalid

Aggregator = Callable[[int, int], int]


@dataclass
class CoGroup:
    aggregators: dict[str, Aggregator]
    partitions: int
    state: dict[str, int] = field(default_factory=dict)
    contributors: dict[str, set[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.aggregators:
            raise Invalid("a cogroup needs at least one stream aggregator")

    def require_copartitioned(self, stream_partitions: int) -> None:
        if stream_partitions != self.partitions:
            raise Invalid(
                f"input has {stream_partitions} partitions but the cogroup "
                f"is on {self.partitions}; a key's records from every stream "
                "must reach one task"
            )

    def apply(self, stream: str, key: str, value: int) -> int:
        if stream not in self.aggregators:
            raise Invalid(
                f"stream '{stream}' has no aggregator; an input with no "
                "defined effect on the state"
            )
        current = self.state.get(key, 0)
        self.state[key] = self.aggregators[stream](current, value)
        self.contributors.setdefault(key, set()).add(stream)
        return self.state[key]

    def completeness(self, key: str) -> str:
        seen = len(self.contributors.get(key, set()))
        total = len(self.aggregators)
        if seen < total:
            return (
                f"key '{key}' has {seen}/{total} stream(s) contributing; an "
                "incomplete value the other streams have not reached yet"
            )
        return f"key '{key}' has all {total} stream(s); a complete value"
