"""Producer idempotence: a producer id and sequence number make a retry harmless.

A producer that sends a batch, times out waiting for the ack, and
retries can write the same batch twice, because the first attempt may
have been persisted before the ack was lost. Idempotent produce
closes that hole without the producer knowing whether the first
attempt landed. Each producer is assigned a producer id, and within
each partition it stamps every batch with a sequence number that
increases by one. The broker remembers, per producer per partition,
the last sequence number it accepted. A batch whose sequence is
exactly one past the last is new: accept it and advance. A batch whose
sequence is less than or equal to the last was already written, this
is the retry, so acknowledge it as a duplicate without appending
again, which is what makes the retry harmless. A batch whose sequence
is more than one past the last means a batch in between was lost, an
out-of-order sequence, and it must be refused rather than accepted,
because accepting it would leave a gap and silently drop the missing
batch. There is also the producer epoch, bumped when a producer is
fenced and restarted, and a batch from an epoch below the current one
is a zombie, an old instance of the producer still trying to write
after a newer instance took over, and it is refused. The tracker
accepts the next sequence, recognizes a duplicate as already written,
and refuses both a gap and a fenced epoch. It reports the highest
sequence retained per producer, because that state is bounded, it is
what a broker must keep in memory for every active producer, and a
producer that never expires is state that never frees."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Fenced, Invalid


@dataclass
class _State:
    epoch: int
    last_sequence: int


@dataclass
class ProducerIdempotence:
    # (producer_id, partition) -> last accepted state
    _seen: dict[tuple[str, int], _State] = field(default_factory=dict)

    def accept(self, producer_id: str, partition: int, epoch: int, sequence: int) -> str:
        key = (producer_id, partition)
        state = self._seen.get(key)
        if state is None:
            if sequence != 0:
                raise Invalid(
                    f"first batch from '{producer_id}' on partition {partition} "
                    f"has sequence {sequence}, not 0; a batch before it was lost"
                )
            self._seen[key] = _State(epoch=epoch, last_sequence=0)
            return "accepted (first batch)"

        if epoch < state.epoch:
            raise Fenced(
                f"epoch {epoch} from '{producer_id}' is below the current "
                f"{state.epoch}; this is a zombie instance, a newer producer "
                "took over, so the write is refused"
            )
        if epoch > state.epoch:
            # a restarted producer resets the sequence under its new epoch
            self._seen[key] = _State(epoch=epoch, last_sequence=sequence)
            return "accepted (new epoch)"

        expected = state.last_sequence + 1
        if sequence == expected:
            state.last_sequence = sequence
            return "accepted"
        if sequence <= state.last_sequence:
            return "duplicate (already written; the retry is harmless)"
        raise Invalid(
            f"sequence {sequence} from '{producer_id}' is past the expected "
            f"{expected}; a batch in between was lost, accepting this would "
            "leave a gap and silently drop the missing batch"
        )

    def high_sequence(self, producer_id: str, partition: int) -> int:
        state = self._seen.get((producer_id, partition))
        if state is None:
            raise Invalid(f"no batches seen from '{producer_id}' on {partition}")
        return state.last_sequence

    def note(self) -> str:
        return (
            f"tracking {len(self._seen)} producer/partition pair(s); this state "
            "is what the broker keeps in memory per active producer, a producer "
            "that never expires is state that never frees"
        )
