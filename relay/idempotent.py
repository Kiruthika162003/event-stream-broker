"""Idempotent producers: retries stop duplicating once the broker remembers.

A producer that never retries loses records to every network
blip; one that retries naively duplicates them, and the
consumer inherits a dedup problem it cannot solve alone. The
broker-side fix is a session: each producer holds an id and a
monotonic sequence number, and the broker remembers the last
sequence it accepted per producer, so a retry of an
already-accepted record is recognized and answered with the
original offset instead of appended again. The sequence must
advance by exactly one; a gap means a record was lost in
flight and silently accepting the later one would leave a hole
the producer does not know about, so the gap is refused loudly.
Producer sessions are fenced by epoch: a producer that
restarts bumps its epoch, and writes from the old epoch are
rejected, because a zombie producer resuming after a network
partition is the classic source of duplicates that survive
every other defense.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Fenced, Invalid


@dataclass
class ProducerSession:
    producer_id: str
    epoch: int
    last_sequence: int = -1
    accepted_offsets: dict[int, int] = field(default_factory=dict)


@dataclass
class IdempotencyGate:
    sessions: dict[str, ProducerSession] = field(
        default_factory=dict
    )
    duplicates_absorbed: int = 0

    def open_session(
        self, producer_id: str, epoch: int
    ) -> ProducerSession:
        held = self.sessions.get(producer_id)
        if held is not None and epoch < held.epoch:
            raise Fenced(
                f"{producer_id} opened epoch {epoch} behind the "
                f"current {held.epoch}; a zombie producer "
                "resuming after a partition is refused before "
                "it can duplicate"
            )
        session = ProducerSession(
            producer_id=producer_id, epoch=epoch
        )
        self.sessions[producer_id] = session
        return session

    def admit(
        self,
        producer_id: str,
        epoch: int,
        sequence: int,
        assign_offset: int,
    ) -> str:
        session = self.sessions.get(producer_id)
        if session is None:
            raise Invalid(
                f"{producer_id} has no open session; register "
                "before producing"
            )
        if epoch < session.epoch:
            raise Fenced(
                f"{producer_id} epoch {epoch} is fenced by "
                f"{session.epoch}"
            )
        if sequence <= session.last_sequence:
            if sequence in session.accepted_offsets:
                self.duplicates_absorbed += 1
                return (
                    f"duplicate: sequence {sequence} already "
                    f"landed at offset "
                    f"{session.accepted_offsets[sequence]}, "
                    "answered with the original, not appended "
                    "again"
                )
            raise Invalid(
                f"sequence {sequence} is below the last "
                f"accepted {session.last_sequence} and was "
                "never seen; this is a producer bug, not a retry"
            )
        if sequence != session.last_sequence + 1:
            raise Invalid(
                f"sequence gap: expected "
                f"{session.last_sequence + 1}, got {sequence}; "
                "a record was lost in flight and accepting this "
                "one would leave a hole the producer cannot see"
            )
        session.last_sequence = sequence
        session.accepted_offsets[sequence] = assign_offset
        return (
            f"accepted sequence {sequence} at offset "
            f"{assign_offset}"
        )

    def ledger(self) -> str:
        return (
            f"{len(self.sessions)} session(s), "
            f"{self.duplicates_absorbed} duplicate(s) absorbed "
            "before they reached a consumer"
        )
