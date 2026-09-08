"""Group generation: a rebalance bumps the id so a stale member's commit is rejected.

A consumer group rebalances whenever membership changes, and each
rebalance produces a new generation, an integer that increments every
time. The generation is how the coordinator tells a current member
from one that has fallen behind. A member that missed the latest
rebalance, because its heartbeat lapsed or a network partition cut it
off, still believes it owns the partitions it had in the previous
generation, and it may try to commit an offset for one of them. If the
coordinator accepted that commit, it would record progress for a
partition that has since been reassigned to another member, and two
consumers would be writing offsets for the same partition, the
overlap a rebalance exists to prevent. So every commit and heartbeat
carries the member's generation, and the coordinator rejects any
request whose generation is not the current one with an illegal-
generation error, which tells the member it is stale and must rejoin.
A generation older than the current is the lagging zombie just
described. A generation newer than the current cannot legitimately
exist, since only the coordinator mints generations, so it is refused
as well rather than trusted. The coordinator holds the current
generation, bumps it on each rebalance, admits a request only when its
generation matches, and refuses one that is behind or ahead. It
reports the current generation and the last rebalance reason, because
a generation climbing quickly is a group rebalancing in a loop,
churning its partition assignments faster than it makes progress, the
symptom that points at a flapping member or too tight a session
timeout."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class GroupGeneration:
    generation: int = 0
    last_reason: str = "initial"

    def rebalance(self, reason: str) -> int:
        self.generation += 1
        self.last_reason = reason
        return self.generation

    def admit(self, member_generation: int, request: str) -> str:
        if member_generation < self.generation:
            raise Invalid(
                f"'{request}' carries generation {member_generation}, current "
                f"is {self.generation}; illegal-generation, the member is stale "
                "and must rejoin, its partitions were reassigned"
            )
        if member_generation > self.generation:
            raise Invalid(
                f"'{request}' carries generation {member_generation}, ahead of "
                f"the current {self.generation}; only the coordinator mints "
                "generations, so this cannot legitimately exist"
            )
        return f"admitted '{request}' at generation {self.generation}"

    def note(self) -> str:
        return (
            f"generation {self.generation}, last rebalance: {self.last_reason}; "
            "a generation climbing fast is a group rebalancing in a loop, "
            "churning assignments faster than it makes progress"
        )
