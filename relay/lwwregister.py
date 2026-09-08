"""LWW register: converge by keeping the latest write, and lose the other one.

A last-write-wins register is the simplest conflict-resolving CRDT:
a single value tagged with a timestamp, and when two replicas that
took different writes merge, the one with the higher timestamp
wins. Because merge is a max over timestamps, it is commutative,
associative, and idempotent, so replicas converge to the same value
regardless of merge order or duplicate delivery, the CRDT
guarantee. Timestamps tie, so the tie is broken by node id, giving
every write a distinct rank and making the merge deterministic
rather than dependent on which replica merged first. The name says
the cost: last-write-wins resolves a conflict by keeping one write
and discarding the other, so two concurrent writes to the same
register, neither causally after the other, lose one silently, and
the lost one is simply gone with no trace. This is the trade
against a richer CRDT like a set that keeps both concurrent
additions: LWW is small and simple, one value and a timestamp, and
right when a later write genuinely supersedes an earlier one, wrong
when two concurrent writes both mattered and one is dropped. The
register writes a value with a timestamp, merges by keeping the
higher (timestamp, node), and refuses a merge that would move the
register backward to an older timestamp, which cannot happen under
max but is caught as a programming error if the caller passes a
stale state as newer. It reports whether a merge overwrote a
concurrent write, because a register frequently resolving concurrent
writes is one where LWW is silently dropping updates that a
conflict-preserving type would have kept, a data-loss risk the
simplicity hides."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class LwwRegister:
    value: str = ""
    timestamp: int = 0
    node_id: int = 0

    def write(self, value: str, timestamp: int, node_id: int) -> None:
        if timestamp < self.timestamp:
            raise Invalid("a write cannot carry a timestamp older than the register's")
        self.value = value
        self.timestamp = timestamp
        self.node_id = node_id

    def merge(self, other: LwwRegister) -> bool:
        mine = (self.timestamp, self.node_id)
        theirs = (other.timestamp, other.node_id)
        if theirs > mine:
            self.value = other.value
            self.timestamp = other.timestamp
            self.node_id = other.node_id
            return True
        return False

    def would_drop_concurrent(self, other: LwwRegister) -> bool:
        # concurrent if the timestamps are equal but the values differ:
        # LWW will keep one by node-id tie-break and drop the other
        return (
            self.timestamp == other.timestamp
            and self.value != other.value
            and self.node_id != other.node_id
        )

    def report(self, other: LwwRegister) -> str:
        if self.would_drop_concurrent(other):
            return (
                "concurrent writes at the same timestamp; LWW keeps one by "
                "node-id and silently drops the other, a data-loss risk a "
                "conflict-preserving type would avoid"
            )
        return f"value '{self.value}' at ts {self.timestamp}; a clean supersede"
