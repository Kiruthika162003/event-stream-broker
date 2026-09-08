"""Become leader: a follower promoted must stop fetching before it serves.

When the controller promotes a broker to lead a partition it was
following, the broker runs a transition that must happen in a
specific order, because the roles of leader and follower are
mutually exclusive on one partition and doing them at once
corrupts the log. The broker was fetching this partition from the
old leader, appending what it received, and as leader it must
instead accept produce and be the source others fetch from, so the
first step is to stop the replica fetcher for this partition: a
broker still fetching from the old leader while also accepting
produce would interleave replicated records and produced records
into one log with two writers, which no offset assignment can
reconcile. Only once fetching has stopped does the broker bump the
leader epoch, marking the start of its term so followers can detect
divergence, and initialize the high watermark from the offsets its
in-sync followers have, since as the new leader it now computes the
watermark rather than receiving it. Only after both does it enable
produce. The transition refuses to accept produce before it
completes, because a produce accepted mid-transition could land at
an offset the watermark logic has not yet accounted for, and it
refuses to become leader for a partition the broker does not host,
an instruction from a controller working from stale replica
assignments. It refuses a leader epoch that does not exceed the
current one, the same monotonicity the epoch cache depends on. The
report states the order taken, because a leader that started
serving before its fetcher stopped is the two-writer bug, and the
sequence is the evidence it did not happen.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid, Missing


@dataclass
class LeaderTransition:
    hosts: bool
    fetching: bool = True
    epoch: int = 0
    serving: bool = False

    def become_leader(self, new_epoch: int, isr_end_offsets: list[int]) -> str:
        if not self.hosts:
            raise Missing(
                "this broker does not host the partition; a stale "
                "controller assignment, refusing to lead it"
            )
        if new_epoch <= self.epoch:
            raise Invalid(
                f"leader epoch {new_epoch} does not exceed the current "
                f"{self.epoch}; epochs only advance"
            )
        # order matters: stop fetching, then epoch, then watermark, then serve
        self.fetching = False
        self.epoch = new_epoch
        watermark = min(isr_end_offsets) if isr_end_offsets else 0
        self.serving = True
        return (
            f"became leader at epoch {new_epoch}: fetcher stopped, then "
            f"watermark set to {watermark}, then produce enabled"
        )

    def accept_produce(self, record: str) -> str:
        if not self.serving:
            raise Invalid(
                f"'{record}' refused: the leader transition is not "
                "complete; a produce now could land at an offset the "
                "watermark logic has not accounted for"
            )
        if self.fetching:
            raise Invalid(
                "still fetching as a follower while leading; two writers "
                "into one log, which no offset assignment reconciles"
            )
        return f"produced '{record}' at epoch {self.epoch}"
