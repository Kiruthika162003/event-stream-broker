"""Coordinator epoch: fence a write from a coordinator that has been replaced.

The transaction coordinator writes transaction state, which producer
is in which transaction and whether it committed, into a log, and if
that coordinator is replaced after a failover, the old one must not be
able to keep writing. A network partition can leave an old coordinator
running, still believing it is in charge, while a new one has taken
over, and if both could write transaction state they would corrupt it,
one committing what the other aborted. The coordinator epoch prevents
this. Each coordinator incarnation holds an epoch, bumped every time a
new coordinator takes over, and every write to the transaction log
carries the writer's epoch. The log accepts a write only if its epoch
is the highest seen; a write carrying an epoch below the highest comes
from a superseded coordinator and is fenced, the same generation
argument that fences a stale group member but applied to the
coordinator itself rather than a consumer. The moment the new
coordinator writes anything with the bumped epoch, the old one's next
write is rejected, so the window where both think they are in charge
closes on the first write rather than lasting until the partition
heals. The guard holds the highest epoch it has accepted, admits a
write at or above it and bumps to a new epoch, fences a write below
it, and refuses an epoch that goes backwards at takeover, because a new
coordinator taking a lower epoch than its predecessor would reopen the
fence it exists to hold shut. It reports the current epoch and the
fenced-write count, because fenced writes accumulating is a split-brain
coordinator actively trying to write, the failure the epoch closes off
made visible."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Fenced, Invalid


@dataclass
class CoordinatorEpoch:
    epoch: int = 0
    _fenced: int = 0

    def take_over(self, new_epoch: int) -> None:
        if new_epoch <= self.epoch:
            raise Invalid(
                f"takeover epoch {new_epoch} does not exceed the current "
                f"{self.epoch}; a new coordinator taking a lower epoch would "
                "reopen the fence"
            )
        self.epoch = new_epoch

    def write(self, writer_epoch: int, state: str) -> str:
        if writer_epoch < self.epoch:
            self._fenced += 1
            raise Fenced(
                f"write '{state}' carries epoch {writer_epoch}, current is "
                f"{self.epoch}; this coordinator was superseded, the write is "
                "fenced to stop a split-brain from corrupting transaction state"
            )
        # a write at the current epoch is from the live coordinator
        return f"accepted '{state}' at epoch {self.epoch}"

    def fenced_count(self) -> int:
        return self._fenced

    def note(self) -> str:
        return (
            f"coordinator epoch {self.epoch}, {self._fenced} write(s) fenced; "
            "fenced writes accumulating is a split-brain coordinator actively "
            "trying to write, the failure the epoch closes off"
        )
