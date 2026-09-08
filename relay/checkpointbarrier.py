"""Checkpoint barrier: snapshot state at a line that crosses every input together.

Exactly-once stream processing needs a consistent snapshot of every
operator's state, consistent meaning taken at the same logical
point in the stream so the snapshot reflects exactly the records
before a chosen cut and none after. A checkpoint barrier draws that
cut: a special marker with a checkpoint id is injected into the
stream and flows through the operators, and when an operator sees
the barrier it snapshots its state, because everything before the
barrier is in the state and everything after is not. The subtlety
is an operator with several inputs: the barrier arrives on each
input at a different time, and snapshotting when the first arrives
would capture records from the faster inputs that are after the cut
on those inputs, an inconsistent snapshot. Alignment fixes it: the
operator waits until the barrier has arrived on every input before
snapshotting, and while it waits it buffers records from the inputs
that already sent the barrier, holding them until after the
snapshot so they land on the correct side of the cut. This
alignment is what makes the snapshot consistent across a graph, and
its cost is the buffering and the wait, which is why a slow input
delays a checkpoint for the whole operator. The coordinator tracks
which inputs have delivered the barrier, snapshots only once all
have aligned, and refuses to snapshot before alignment, the
inconsistent-cut bug. It refuses a barrier id that does not exceed
the last checkpoint's, since ids are monotonic and an out-of-order
barrier is a bug, and reports how many inputs are still awaited,
because a checkpoint stuck aligning is one input slow to deliver
its barrier, the stall to chase."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class BarrierAligner:
    inputs: set[str]
    last_checkpoint: int = -1
    _current: int = -1
    arrived: set[str] = field(default_factory=set)
    buffered: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.inputs:
            raise Invalid("an operator needs at least one input")

    def receive_barrier(self, channel: str, checkpoint_id: int) -> str:
        if channel not in self.inputs:
            raise Invalid(f"barrier on unknown input '{channel}'")
        if self._current < 0:
            if checkpoint_id <= self.last_checkpoint:
                raise Invalid(
                    f"checkpoint {checkpoint_id} does not exceed the last "
                    f"{self.last_checkpoint}; barrier ids are monotonic"
                )
            self._current = checkpoint_id
        self.arrived.add(channel)
        return f"barrier {checkpoint_id} on '{channel}', {self.awaiting()} awaited"

    def buffer_record(self, channel: str) -> None:
        # a record arriving on an input that already sent the barrier is held
        if channel in self.arrived:
            self.buffered[channel] = self.buffered.get(channel, 0) + 1

    def awaiting(self) -> int:
        return len(self.inputs) - len(self.arrived)

    def aligned(self) -> bool:
        return self.arrived == self.inputs

    def snapshot(self) -> str:
        if not self.aligned():
            raise Invalid(
                f"cannot snapshot with {self.awaiting()} input(s) not yet "
                "aligned; snapshotting now captures records after the cut on "
                "the faster inputs, an inconsistent snapshot"
            )
        cid = self._current
        self.last_checkpoint = cid
        self._current = -1
        self.arrived.clear()
        released = sum(self.buffered.values())
        self.buffered.clear()
        return (
            f"checkpoint {cid} snapshotted after alignment; {released} "
            "buffered record(s) released to the correct side of the cut"
        )
