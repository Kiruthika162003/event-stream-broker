"""Auto-commit interval: how much you replay on a crash, priced in overhead.

A consumer that commits its offset automatically on an interval
trades two costs against each other, and the interval is the dial
between them. Commit often and the overhead of commit requests
rises, each one a round trip to the coordinator; commit rarely
and the window of records processed-but-not-committed grows, so a
crash replays everything back to the last commit, and at
at-least-once that means reprocessing, at every side effect fired
again. The interval's real meaning is the size of that replay
window, and the calculator makes it concrete: at a given record
rate, an interval of N ticks means a crash replays up to N times
the rate in records, a number the operator can weigh against the
cost of reprocessing them. The subtlety auto-commit hides is that
it commits on poll, not on process, so it can commit an offset
for records fetched but not yet fully processed, and a crash then
loses them, turning at-least-once into at-most-once by accident,
which is why a consumer that must not lose records should commit
manually after processing rather than trust the auto-commit
timing. The calculator names that trap: auto-commit is a
convenience for consumers that tolerate a replay window, not a
correctness mechanism, and a consumer using it while believing it
has exactly-once has chosen a delivery guarantee it does not have.
The report states the replay window in records so the interval is
a decision about data, not a number copied from a default.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class AutoCommitPolicy:
    interval_ticks: int
    record_rate: float

    def __post_init__(self) -> None:
        if self.interval_ticks < 1 or self.record_rate < 0:
            raise Invalid(
                "interval positive and rate nonnegative"
            )

    def replay_window_records(self) -> int:
        return int(self.interval_ticks * self.record_rate)

    def describe(self) -> str:
        window = self.replay_window_records()
        return (
            f"interval {self.interval_ticks} at rate "
            f"{self.record_rate}/tick: a crash replays up to "
            f"{window} record(s), the size of the window weighed "
            "against the cost of reprocessing them"
        )

    def guarantee_note(self, commits_on_poll: bool) -> str:
        if commits_on_poll:
            return (
                "auto-commit commits on poll not process, so a "
                "crash can lose fetched-but-unprocessed records, "
                "turning at-least-once into at-most-once by "
                "accident; a consumer that must not lose records "
                "commits manually after processing"
            )
        return (
            "committing after processing keeps at-least-once; the "
            "replay window is reprocessing, not loss"
        )
