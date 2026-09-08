"""Callback order: a send's completion fires after the ones before it, per partition.

A producer's send is asynchronous: it returns a future and a
callback fires when the broker acknowledges the record. The
guarantee that makes those callbacks usable for ordered work is
that, within a partition, callbacks fire in the order the records
were sent, so the callback for a record at offset five fires after
the callback for offset four on the same partition, and code in a
callback can assume every earlier record on its partition has
already completed. This lets a producer do things like advance an
external cursor in a callback, knowing the callback order matches
the log order. The guarantee is per partition, not global: two
callbacks for records on different partitions can fire in either
order, because the partitions complete independently, so callback
order carries the same scoping as record order. The dispatcher
enforces per-partition ordering by holding a callback until every
earlier record on its partition has had its callback fire, so a
record whose acknowledgement arrives out of order, which can happen
when a retry reorders acknowledgements, does not fire its callback
early and violate the order the caller relies on. It refuses to
dispatch a callback for a record before its predecessor on the same
partition, buffering it until the gap fills, and refuses to
dispatch the same record's callback twice, the double-fire a retry
could otherwise cause. It reports how many callbacks are buffered
waiting for an earlier one, because a growing buffer is a record
whose acknowledgement is stuck, holding back the callbacks of every
record sent after it on that partition, a head-of-line stall in the
completion path that a caller doing ordered work in callbacks would
otherwise experience as silence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class CallbackDispatcher:
    next_to_fire: dict[str, int] = field(default_factory=dict)
    buffered: dict[str, set[int]] = field(default_factory=dict)
    fired: dict[str, set[int]] = field(default_factory=dict)

    def acknowledge(self, partition: str, offset: int) -> list[int]:
        self.fired.setdefault(partition, set())
        self.buffered.setdefault(partition, set())
        if offset in self.fired[partition] or offset in self.buffered[partition]:
            raise Invalid(
                f"offset {offset} on '{partition}' already acknowledged; a "
                "double-fire a retry could cause"
            )
        expected = self.next_to_fire.get(partition, 0)
        if offset < expected:
            raise Invalid(
                f"offset {offset} is behind the next expected {expected} on "
                f"'{partition}'; its callback already fired"
            )
        self.buffered[partition].add(offset)
        return self._drain(partition)

    def _drain(self, partition: str) -> list[int]:
        expected = self.next_to_fire.get(partition, 0)
        fired_now = []
        while expected in self.buffered[partition]:
            self.buffered[partition].discard(expected)
            self.fired[partition].add(expected)
            fired_now.append(expected)
            expected += 1
        self.next_to_fire[partition] = expected
        return fired_now

    def pending(self, partition: str) -> int:
        return len(self.buffered.get(partition, set()))

    def stall_note(self, partition: str) -> str:
        n = self.pending(partition)
        if n == 0:
            return f"'{partition}': no callbacks waiting; completions flow in order"
        return (
            f"'{partition}': {n} callback(s) buffered behind a stuck "
            "acknowledgement, a head-of-line stall in the completion path"
        )
