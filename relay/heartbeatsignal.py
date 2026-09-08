"""Heartbeat signal: the rebalance is announced in the reply to a heartbeat.

A group member sends heartbeats to prove it is alive, but the
heartbeat reply carries information back, and that reply is how a
member learns a rebalance has started. While the group is stable
the coordinator answers a heartbeat with a plain acknowledgement,
but once a rebalance begins, because a member joined, left, or was
removed, the coordinator answers every heartbeat with a rebalance-
in-progress signal, which is the member's cue to stop consuming and
rejoin. This is why members do not poll for rebalances: they find
out through the heartbeat they were already sending, so the signal
reaches every member within one heartbeat interval of the rebalance
starting. The member's generation is the guard against acting on
stale state. Each completed rebalance bumps the generation, and a
member heartbeats with the generation it last joined, so a member
heartbeating with a generation older than the current one has
missed a rebalance entirely, and the coordinator fences it with an
illegal-generation error rather than acknowledging, forcing it to
rejoin from scratch. The coordinator refuses to acknowledge a stale
generation as if current, because a member that kept consuming on a
dead generation is a double-owner processing partitions now
assigned to someone else. The model answers a heartbeat given the
member's generation and the group's state, returning acknowledge,
rebalance-in-progress, or fenced, and it refuses a heartbeat from a
member the coordinator does not know, an unregistered member whose
heartbeat is either very late or from a different group. The report
states how long a rebalance signal has been outstanding for a
member, because a member still heartbeating with the old generation
long after the signal is one ignoring the cue and holding
partitions it should have revoked.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Fenced, Invalid

ACK = "acknowledged"
REBALANCE = "rebalance-in-progress"


@dataclass
class HeartbeatCoordinator:
    generation: int
    rebalancing: bool = False
    members: set[str] = field(default_factory=set)

    def register(self, member: str) -> None:
        self.members.add(member)

    def start_rebalance(self) -> None:
        self.rebalancing = True

    def complete_rebalance(self) -> None:
        self.rebalancing = False
        self.generation += 1

    def heartbeat(self, member: str, member_generation: int) -> str:
        if member not in self.members:
            raise Invalid(
                f"{member} is not a known member; its heartbeat is "
                "very late or from a different group"
            )
        if member_generation < self.generation:
            raise Fenced(
                f"{member} heartbeat with generation "
                f"{member_generation} < current {self.generation}; it "
                "missed a rebalance and would be a double-owner if "
                "acknowledged, so it must rejoin from scratch"
            )
        if self.rebalancing:
            return REBALANCE
        return ACK
