"""Acks: how long the producer waits, and exactly what it is promised.

The acknowledgement mode is the producer's durability-latency
dial, and its three settings make three different promises that
teams routinely confuse. Acks-none returns the instant the
leader receives the bytes, before they touch disk or a
follower, so it is fast and promises nothing: a leader crash
loses the record and the producer never knew. Acks-leader
returns once the leader has the record durably, surviving a
follower's death but not the leader's. Acks-all returns only
when the in-sync set has it, surviving any single failure the
replication factor covers. The resolver refuses to let a
producer request acks-all against an in-sync set already below
the min floor, because that request would block forever waiting
for replicas that policy already removed, and a silent
indefinite hang is a worse failure than an honest one. Each
resolution states the failure the producer just chose to
survive and the one it chose to accept, because a durability
mode picked without knowing its blast radius is a mode picked
by accident.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

NONE = "none"
LEADER = "leader"
ALL = "all"
MODES = (NONE, LEADER, ALL)


@dataclass(frozen=True)
class Acknowledgement:
    mode: str
    durable: bool
    survives: str
    accepts: str

    def line(self) -> str:
        return (
            f"acks={self.mode}: survives {self.survives}, "
            f"accepts loss on {self.accepts}"
        )


def resolve_ack(
    mode: str, in_sync_count: int, min_in_sync: int
) -> Acknowledgement:
    if mode not in MODES:
        raise Invalid(f"unknown acks mode {mode}; one of {MODES}")
    if mode == NONE:
        return Acknowledgement(
            mode=NONE,
            durable=False,
            survives="nothing",
            accepts="a leader crash the producer never hears about",
        )
    if mode == LEADER:
        return Acknowledgement(
            mode=LEADER,
            durable=True,
            survives="a follower's death",
            accepts="a leader crash before replication",
        )
    if in_sync_count < min_in_sync:
        raise Invalid(
            f"acks=all against an in-sync set of "
            f"{in_sync_count} below the floor {min_in_sync} "
            "would block forever waiting for replicas policy "
            "already removed; an honest failure beats a silent "
            "hang"
        )
    return Acknowledgement(
        mode=ALL,
        durable=True,
        survives=f"any single failure the {in_sync_count}-replica "
        "set covers",
        accepts="unavailability if the set drops below the floor",
    )
