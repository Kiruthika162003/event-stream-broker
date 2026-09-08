"""Causal delivery: hold a message until its causes have been delivered.

A network reorders messages, so a receiver can get an effect before
its cause: a reply before the message it replies to, an update
before the create it depends on. Causal-order delivery prevents
that. Each message carries the set of messages it causally depends
on, the ones that must be delivered before it makes sense, and the
receiver, rather than delivering a message the instant it arrives,
delivers it only once every message in its dependency set has
already been delivered, buffering it until then. So a message that
arrives early, before a cause it depends on, waits in the buffer,
and when the cause finally arrives and is delivered, the waiting
message becomes deliverable and is released, possibly unblocking
others that depended on it in turn. This guarantees the receiver
sees messages in an order consistent with causality even though the
network delivered them in some other order, which is weaker than a
total order, concurrent messages can still be delivered in either
order, but strong enough that no effect precedes its cause. The
buffer holds an early message until its dependencies are met, and
releasing one may cascade, so delivery re-checks the buffer after
each release. The deliverer accepts a message with its dependency
set, delivers it immediately if its dependencies are already met,
buffers it otherwise, and releases buffered messages as their
dependencies arrive. It refuses to force-deliver a message with
unmet dependencies, the reordering the buffer exists to prevent, and
reports the buffered count, because a buffer that keeps growing is a
receiver waiting on a dependency that was lost or will never arrive,
a stuck causal chain rather than a transient reorder."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class CausalDelivery:
    delivered: set[str] = field(default_factory=set)
    buffer: dict[str, set[str]] = field(default_factory=dict)

    def _deliverable(self, deps: set[str]) -> bool:
        return deps <= self.delivered

    def accept(self, message: str, deps: set[str]) -> list[str]:
        if self._deliverable(deps):
            return self._deliver(message)
        self.buffer[message] = set(deps)
        return []

    def _deliver(self, message: str) -> list[str]:
        released = [message]
        self.delivered.add(message)
        # releasing one may unblock others; re-check until nothing new frees
        changed = True
        while changed:
            changed = False
            for msg, deps in list(self.buffer.items()):
                if self._deliverable(deps):
                    del self.buffer[msg]
                    self.delivered.add(msg)
                    released.append(msg)
                    changed = True
        return released

    def force_deliver(self, message: str, deps: set[str]) -> None:
        if not self._deliverable(deps):
            missing = deps - self.delivered
            raise Invalid(
                f"'{message}' depends on undelivered {sorted(missing)}; "
                "delivering it now shows an effect before its cause, the "
                "reordering causal delivery prevents"
            )

    def buffered_note(self) -> str:
        n = len(self.buffer)
        return (
            f"{n} message(s) buffered awaiting dependencies; a growing buffer "
            "is a receiver waiting on a lost dependency, a stuck causal chain "
            "not a transient reorder"
        )
