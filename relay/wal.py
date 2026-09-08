"""Write-ahead log: write the intent durably first, so a crash can replay it.

Any state a system must not lose across a crash is protected by a
write-ahead log: before applying a change to the in-memory or
on-disk state, the change is appended to the WAL and made durable,
so that if the system crashes after the append but before or during
the apply, recovery replays the WAL and re-applies the change,
reaching the state the WAL says it should have. The ordering is the
whole guarantee, and it is the reverse of intuition: the log is
written before the thing it describes, not after, because a change
applied but not logged is lost on a crash with no record to replay,
while a change logged but not yet applied is recovered. This is why
the append must be durable before the apply proceeds, not
concurrently. The WAL grows without bound if only appended, so a
checkpoint bounds it: a checkpoint records that the state is durable
up to a WAL offset, meaning every change before it is safely in the
state and need not be replayed, so the WAL before the checkpoint can
be truncated, and recovery replays only from the last checkpoint
forward. The log appends an intent, marks it durable, applies only
after durability, checkpoints when the state is persisted, and
truncates the WAL before a checkpoint. It refuses to apply a change
whose WAL append is not yet durable, the ordering violation that
loses data, and refuses to truncate the WAL past the checkpoint,
which would discard log entries recovery still needs. It reports
the replay length after the last checkpoint, because a WAL far
longer than its checkpoint interval is one checkpointing too rarely,
making recovery replay more than it needs, the same lesson as every
snapshot in this package."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class WriteAheadLog:
    entries: list[str] = field(default_factory=list)
    durable_to: int = 0
    applied_to: int = 0
    checkpoint: int = 0

    def append(self, intent: str) -> int:
        self.entries.append(intent)
        return len(self.entries) - 1

    def mark_durable(self, offset: int) -> None:
        self.durable_to = max(self.durable_to, offset + 1)

    def apply(self, offset: int) -> str:
        if offset >= self.durable_to:
            raise Invalid(
                f"entry {offset} is not durable yet (durable to "
                f"{self.durable_to}); applying before the log is durable loses "
                "it on a crash, the ordering the WAL exists to enforce"
            )
        if offset != self.applied_to:
            raise Invalid(
                f"entries apply in order; expected {self.applied_to}, got {offset}"
            )
        self.applied_to = offset + 1
        return f"applied entry {offset}"

    def take_checkpoint(self) -> str:
        self.checkpoint = self.applied_to
        return f"checkpoint at {self.checkpoint}; state durable up to there"

    def truncate(self) -> str:
        return (
            f"WAL before the checkpoint {self.checkpoint} truncated; recovery "
            "replays from there"
        )

    def replay_length(self) -> str:
        length = len(self.entries) - self.checkpoint
        return (
            f"{length} entry(ies) to replay after the checkpoint; a WAL far "
            "longer than its checkpoint interval checkpoints too rarely and "
            "recovers more than it needs"
        )
