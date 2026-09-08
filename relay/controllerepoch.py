"""Controller epoch: one broker runs the cluster, and stale ones are fenced.

Exactly one broker at a time is the controller, the broker that
assigns partitions, drives elections, and edits cluster metadata,
and the controller can fail and be replaced like any other role,
so it needs its own fencing separate from partition leadership.
The controller epoch is a cluster-wide counter that increments
each time a new controller takes over, and every metadata change
the controller makes carries its epoch. A broker receiving a
metadata change checks the epoch: a change from an epoch older
than the one it has seen is from a deposed controller that has
not yet realized it lost the role, and applying it would let a
zombie controller reassign partitions the real controller already
moved, the split brain at the cluster level rather than the
partition level. So stale-epoch changes are rejected. The subtle
requirement is that the epoch is monotonic across the whole
cluster and every broker agrees on the current one, because a
broker that accepted a stale change while another rejected it
would leave the two with divergent cluster metadata, which is the
exact corruption the epoch prevents at the partition level now
happening to the map of the whole cluster. The fencer tracks the
highest epoch seen and rejects anything below it, names the gap
on rejection because an operator seeing metadata changes bounce
needs to know a deposed controller is still trying, and confirms
a new controller's takeover only when its epoch exceeds the
current, because a new controller claiming an epoch not greater
than the old one has not actually superseded it.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Fenced, Invalid


@dataclass
class ControllerFencer:
    current_epoch: int = 0
    controller: str = ""
    rejected_stale: int = 0

    def take_over(self, broker: str, epoch: int) -> str:
        if epoch <= self.current_epoch and self.current_epoch != 0:
            raise Invalid(
                f"{broker} claims epoch {epoch} not greater than "
                f"the current {self.current_epoch}; a new "
                "controller must supersede, not tie"
            )
        self.current_epoch = epoch
        self.controller = broker
        return (
            f"{broker} is controller at epoch {epoch}; earlier "
            "controllers are now fenced"
        )

    def apply_change(self, from_epoch: int, change: str) -> str:
        if from_epoch < self.current_epoch:
            self.rejected_stale += 1
            raise Fenced(
                f"metadata change '{change}' from epoch "
                f"{from_epoch} rejected; the current controller "
                f"epoch is {self.current_epoch}, and a deposed "
                "controller reassigning partitions is cluster-"
                "level split brain"
            )
        if from_epoch > self.current_epoch:
            raise Invalid(
                "a change from a future epoch means this broker "
                "missed a takeover; refresh before applying"
            )
        return f"applied '{change}' at epoch {from_epoch}"

    def report(self) -> str:
        return (
            f"controller {self.controller} at epoch "
            f"{self.current_epoch}, {self.rejected_stale} stale "
            "change(s) fenced; a deposed controller still trying "
            "shows here"
        )
