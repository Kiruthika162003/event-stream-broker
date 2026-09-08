"""Lamport clock: order events across nodes without trusting wall clocks.

Ordering events that happen on different brokers cannot rely on
their wall clocks, because those clocks drift and skew, so an event
stamped later by one broker's clock may really have happened before
an event stamped earlier by another's. A Lamport logical clock
orders events by causality instead of time: each node keeps a
counter, incremented on every local event, and when a node receives
a message it sets its counter to one past the larger of its own and
the message's timestamp, so the receive is stamped after the send
no matter what the wall clocks say. This gives the happens-before
relation: if event A causally precedes event B, A's Lamport
timestamp is less than B's, which is exactly what is needed to
reason about causality, an update must not be applied before the
one it depends on. The relation is a partial order, not total,
because two events on different nodes with no message between them
are concurrent and can get the same or unordered timestamps, and
Lamport timestamps alone cannot tell concurrent from ordered. A
total order, when one is needed, is made by breaking ties with the
node id, so equal timestamps order by node, giving every event a
distinct rank that still respects causality. The clock ticks on a
local event, updates on a receive, and its guarantee is one-
directional: A before B implies a smaller timestamp, but a smaller
timestamp does not imply A before B, because the two could be
concurrent, and treating a smaller Lamport timestamp as proof of
happens-before is the classic misuse. The clock refuses a received
timestamp that is negative, and reports the current value; it never
goes backwards, since both tick and receive only advance it, the
property that makes the order it defines consistent."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class LamportClock:
    node_id: int
    counter: int = 0

    def __post_init__(self) -> None:
        if self.node_id < 0:
            raise Invalid("node id cannot be negative")

    def tick(self) -> int:
        self.counter += 1
        return self.counter

    def on_receive(self, message_timestamp: int) -> int:
        if message_timestamp < 0:
            raise Invalid("a received Lamport timestamp cannot be negative")
        self.counter = max(self.counter, message_timestamp) + 1
        return self.counter

    def stamp(self) -> tuple[int, int]:
        # a total-order stamp: (counter, node_id) breaks ties by node
        return (self.counter, self.node_id)

    @staticmethod
    def happens_before(a: tuple[int, int], b: tuple[int, int]) -> bool:
        # total order over (counter, node); NOT proof of causality when
        # the two events are concurrent, only a consistent tie-break
        return a < b
