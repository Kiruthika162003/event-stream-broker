"""Flow control: the receiver grants credit, and the sender spends only that.

Rate limiting bounds how fast a sender sends by time, but that does
not directly protect a receiver's buffer, because a receiver that
slows down for a moment can still be overrun by a sender at its
allowed rate. Credit-based flow control bounds it by space instead:
the receiver advertises a credit, the number of messages it has
buffer room for, and the sender may send at most that many,
decrementing its credit with each, so it never sends more than the
receiver can hold. As the receiver processes messages and frees
buffer, it grants more credit back to the sender, which refills the
sender's allowance, and a sender that has spent all its credit must
wait until more is granted. This couples the sender's rate to the
receiver's actual processing rate, not a fixed number: a receiver
that speeds up grants credit faster and the sender speeds up with
it, and one that slows grants slower and the sender slows, automatic
back-pressure without a configured rate. It is the mechanism behind
reactive-stream demand and protocol-level flow control, and it
suits a broker's fetch path where a slow consumer should naturally
throttle the data pushed to it. The controller grants credit,
spends it per send, refuses a send with no credit remaining, and
refills as the receiver processes. It refuses to grant negative
credit, and refuses to spend more than is held, the overrun the
scheme prevents. It reports the outstanding credit, because a sender
often at zero credit is one faster than the receiver can process,
the back-pressure working, while a sender never near zero is one the
receiver keeps well ahead of, with credit to spare."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class FlowControl:
    credit: int = 0

    def grant(self, amount: int) -> int:
        if amount < 0:
            raise Invalid("cannot grant negative credit")
        self.credit += amount
        return self.credit

    def send(self, count: int = 1) -> str:
        if count < 1:
            raise Invalid("a send is at least one message")
        if count > self.credit:
            raise Invalid(
                f"send of {count} exceeds credit {self.credit}; the sender must "
                "wait for more, the overrun flow control prevents"
            )
        self.credit -= count
        return f"sent {count}; {self.credit} credit remaining"

    def processed(self, count: int) -> int:
        # the receiver frees buffer and grants that much credit back
        return self.grant(count)

    def report(self) -> str:
        if self.credit == 0:
            return (
                "no credit; the sender is faster than the receiver processes, "
                "the back-pressure working as intended"
            )
        return f"{self.credit} credit outstanding; the receiver is keeping ahead"
