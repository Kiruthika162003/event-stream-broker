"""Sequencer: one monotonic counter gives a total order, and one bottleneck.

Some systems need a total order over events from many producers, a
single sequence in which everything happened, and the simplest way
to get it is a sequencer: one service that hands out strictly
increasing sequence numbers, so every event stamped by it has a
distinct rank and the ranks define the order. This is stronger than
the partial order a Lamport or vector clock gives, because it
orders even concurrent events, but it pays for that strength with a
single point through which every event must pass, which bounds the
whole system's throughput to how fast one sequencer can stamp, and
makes the sequencer a single point of failure. Two techniques
soften those costs. Batching amortizes the round trip: a client
requests a range of sequence numbers at once and hands them out
locally, so it talks to the sequencer once per range rather than
once per event, trading a little wasted range on a crash for far
less traffic. Failover handles the single point: a standby
sequencer takes over, and it must start issuing above the highest
number the old sequencer ever handed out, or it would reissue
numbers already used and break the total order, so the failover
leaves a safe gap by jumping ahead past any range that might have
been handed out. The sequencer issues the next number or a batch
range, and on failover resumes above a floor. It refuses to issue a
number at or below one already issued, the monotonicity the order
depends on, and refuses a failover floor below the highest issued,
which would reuse numbers. It reports the throughput ceiling, the
numbers per second one sequencer can stamp, because a system
approaching it is one where the sequencer, not the brokers, is the
bottleneck, the cost of a total order."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class Sequencer:
    next_seq: int = 0
    highest_issued: int = -1

    def issue(self) -> int:
        seq = self.next_seq
        self.next_seq += 1
        self.highest_issued = seq
        return seq

    def issue_batch(self, size: int) -> tuple[int, int]:
        if size < 1:
            raise Invalid("a batch is at least one number")
        start = self.next_seq
        self.next_seq += size
        self.highest_issued = self.next_seq - 1
        return (start, self.highest_issued)  # inclusive range for local handout

    def failover_resume(self, floor: int) -> str:
        if floor <= self.highest_issued:
            raise Invalid(
                f"failover floor {floor} is not above the highest issued "
                f"{self.highest_issued}; resuming there would reissue numbers "
                "and break the total order"
            )
        self.next_seq = floor
        return f"standby resumes at {floor}, safely above the old sequencer's range"

    def throughput_note(self, per_second: int) -> str:
        return (
            f"one sequencer stamps ~{per_second}/s; a system approaching that "
            "has the sequencer, not the brokers, as its bottleneck, the cost of "
            "a total order"
        )
