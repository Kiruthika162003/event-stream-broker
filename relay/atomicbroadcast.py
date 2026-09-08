"""Atomic broadcast: everyone delivers the same messages in the same order.

Total-order broadcast, also called atomic broadcast, is the
abstraction underneath much of this whole package: a way to send
messages so that every node delivers the same set of messages in
the same order. It is exactly what a replicated log provides, which
is why the log is not just storage but a coordination primitive: the
offset is the total order, and every consumer reading the log sees
the same records in the same offset order, so a set of nodes that
each apply the log's records in order end up in the same state, the
foundation of state-machine replication. The abstraction has two
properties. Agreement: if any node delivers a message, every
correct node eventually delivers it, no node is left out. Total
order: any two nodes that deliver two messages deliver them in the
same order, never one seeing A before B and another B before A.
Together they mean the log defines a single history everyone agrees
on. A node delivers in order by tracking the next sequence it
expects and delivering only that, buffering anything ahead until the
gap fills, so it never delivers out of order or skips. This is why
consensus and atomic broadcast are equivalent: agreeing on the next
message in the order is agreeing on a value, and the leader-based
log the rest of this package builds is one implementation of it.
The delivery tracks the next expected sequence, delivers it and any
buffered successors, and buffers a message ahead of the gap. It
refuses to deliver a message that skips the next expected sequence,
the out-of-order delivery that breaks total order, and reports the
delivered prefix, because a node whose delivered sequence lags the
others is one behind on the shared history, catching up rather than
diverging."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class AtomicBroadcast:
    next_expected: int = 0
    buffer: dict[int, str] = field(default_factory=dict)
    delivered: list[str] = field(default_factory=list)

    def receive(self, sequence: int, message: str) -> list[str]:
        if sequence < self.next_expected:
            return []  # a duplicate of something already delivered
        self.buffer[sequence] = message
        just_delivered = []
        while self.next_expected in self.buffer:
            just_delivered.append(self.buffer.pop(self.next_expected))
            self.delivered.append(just_delivered[-1])
            self.next_expected += 1
        return just_delivered

    def deliver_in_order(self, sequence: int, message: str) -> str:
        if sequence != self.next_expected:
            raise Invalid(
                f"sequence {sequence} skips the next expected "
                f"{self.next_expected}; delivering it breaks total order, "
                "buffer it until the gap fills"
            )
        self.delivered.append(message)
        self.next_expected += 1
        return f"delivered {sequence}"

    def report(self) -> str:
        return (
            f"delivered through sequence {self.next_expected - 1}, "
            f"{len(self.buffer)} buffered ahead of the gap; a lagging node is "
            "behind on the shared history, catching up not diverging"
        )
