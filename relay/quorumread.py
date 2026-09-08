"""Quorum read: a read sees the latest write only if the quorums overlap.

A replicated store with N copies lets a client tune consistency
against availability by choosing how many copies a write must reach
and how many a read must consult. A write goes to W copies before
it is acknowledged, a read consults R copies and takes the newest
answer, and the rule that makes a read see the latest write is that
the read set and the write set must overlap in at least one copy,
which holds exactly when R plus W is greater than N. If they
overlap, the read touches at least one copy that took the write and
sees it; if R plus W is N or less, a read and a write can land on
disjoint copies and the read misses the write, returning stale.
This one inequality is the whole knob. Pushing W up makes writes
more durable and reads cheaper but writes less available, because a
write needs more copies up to accept; pushing R up does the mirror.
Common points on the line are W equal to N for read-one durability,
R equal to N for write-one freshness, and R and W both a majority
so any two quorums overlap and both reads and writes tolerate a
minority failing. The calculator decides whether a given N, R, W
guarantees a read sees the latest write, and names the failures it
tolerates: a write survives up to N minus W copies failing, a read
up to N minus R, so the choice is a durability-availability
position, not a single best. It refuses R or W above N, which
cannot be met, or below one, which consults no copy, and reports
whether the configuration is consistent and how many failures each
side tolerates, so the tradeoff is chosen with both numbers in
view rather than by copying a default."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class QuorumConfig:
    replicas: int
    read_quorum: int
    write_quorum: int

    def __post_init__(self) -> None:
        if self.replicas < 1:
            raise Invalid("need at least one replica")
        for q in (self.read_quorum, self.write_quorum):
            if not 1 <= q <= self.replicas:
                raise Invalid(
                    f"a quorum must be between 1 and {self.replicas}; a "
                    "quorum above N cannot be met and below 1 consults no copy"
                )

    def is_consistent(self) -> bool:
        return self.read_quorum + self.write_quorum > self.replicas

    def write_failures_tolerated(self) -> int:
        return self.replicas - self.write_quorum

    def read_failures_tolerated(self) -> int:
        return self.replicas - self.read_quorum

    def report(self) -> str:
        state = "consistent" if self.is_consistent() else "STALE-POSSIBLE"
        return (
            f"R={self.read_quorum} W={self.write_quorum} N={self.replicas}: "
            f"{state} (R+W {'>' if self.is_consistent() else '<='} N); a write "
            f"tolerates {self.write_failures_tolerated()} failure(s), a read "
            f"{self.read_failures_tolerated()}, a durability-availability "
            "position, not a single best"
        )
