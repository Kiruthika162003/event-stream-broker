"""Producer id expiry: idle sequence state is reclaimed, and that has a cost.

To detect a duplicate the broker remembers, per producer id, the
last sequence number it accepted, so a retried batch with a
sequence it already saw is dropped rather than appended twice. That
memory is not free: a broker serving many short-lived producers
accumulates sequence state for producer ids that will never write
again, so the state is expired after the producer has been idle
longer than a timeout, freeing the memory. Expiry is safe only
because it is tied to the idempotence window: a producer idle that
long has no in-flight batch that could still be retried, so
forgetting its last sequence cannot cause a duplicate to slip
through, since there is no retry left to deduplicate against. The
cost lands on a producer that returns after its state expired: its
next batch carries a sequence continuing from where it left off,
but the broker has forgotten the baseline, so the broker cannot
tell whether that sequence is a fresh write or a duplicate, and it
must treat the producer as new, which means the producer has to
re-initialize and get a fresh producer id rather than resume. The
tracker refuses to expire a producer with an open transaction,
because expiring transactional state mid-transaction would strand
the transaction with no coordinator memory of it. The report
states how much sequence state is live versus expirable, because a
broker under memory pressure from producer state needs to know how
much is genuinely active versus idle producers it is still
tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class ProducerState:
    producer_id: int
    last_seq: int
    idle_ticks: int
    in_transaction: bool = False


@dataclass
class ProducerRegistry:
    timeout_ticks: int
    states: dict[int, ProducerState] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timeout_ticks < 1:
            raise Invalid("the idle timeout must be positive")

    def track(self, state: ProducerState) -> None:
        self.states[state.producer_id] = state

    def expire_idle(self) -> list[int]:
        expired = []
        for pid, st in list(self.states.items()):
            if st.idle_ticks < self.timeout_ticks:
                continue
            if st.in_transaction:
                raise Invalid(
                    f"producer {pid} is idle past the timeout but "
                    "has an open transaction; expiring it would "
                    "strand the transaction with no memory of it"
                )
            del self.states[pid]
            expired.append(pid)
        return expired

    def resume_note(self, producer_id: int) -> str:
        if producer_id in self.states:
            return (
                f"producer {producer_id} still tracked; it resumes "
                "from its last sequence and dedup still holds"
            )
        return (
            f"producer {producer_id} was expired; the broker "
            "forgot its baseline sequence and cannot tell a fresh "
            "write from a duplicate, so it must re-initialize and "
            "get a new producer id rather than resume"
        )

    def live_versus_expirable(self) -> str:
        live = sum(
            1
            for s in self.states.values()
            if s.idle_ticks < self.timeout_ticks
        )
        expirable = len(self.states) - live
        return (
            f"{live} live producer(s), {expirable} idle past the "
            "timeout and expirable; memory pressure from producer "
            "state is mostly the idle ones still tracked"
        )
