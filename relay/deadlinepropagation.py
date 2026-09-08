"""Deadline propagation: carry the clock down the call chain, not just the request.

A request that enters with a deadline, answer within two seconds or
the client gives up, often fans out into several internal calls,
and the deadline must travel with them or it means nothing. If each
internal call used its own fresh timeout instead of the original
deadline, a chain of three calls each with a two-second timeout
could take six seconds while the client gave up at two, so every
call after the client left is work done for a response no one will
read, load spent on nothing. Deadline propagation passes the
absolute deadline down the chain, and each call, before it starts,
checks the time remaining until that deadline and refuses to begin
if it has already passed or if there is not enough left to finish,
failing fast rather than starting work that will be discarded. This
turns the deadline from a per-call timeout into an end-to-end
budget the whole chain shares, so the total time is bounded by the
original deadline no matter how deep the chain, and a slow early
call leaves less budget for the later ones, which is correct
because the client's clock does not stop for the internal
structure. The propagator computes the remaining budget at each
hop, permits a call only while budget remains, and refuses one past
the deadline, naming that the work would be discarded. It also
refuses a call whose own estimated cost exceeds the remaining
budget, because starting a call that cannot finish in time wastes
the budget a shorter alternative might have used. It reports the
remaining budget at a hop, because a chain that routinely arrives
at its last hop with no budget left is one whose early hops are
slow, spending the deadline before the work that needed it, a
place to speed up rather than a place to raise the deadline.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class Deadline:
    deadline_at: int

    def remaining(self, now: int) -> int:
        return self.deadline_at - now

    def expired(self, now: int) -> bool:
        return now >= self.deadline_at

    def begin_call(self, now: int, estimated_cost: int) -> str:
        if self.expired(now):
            raise Invalid(
                f"deadline passed at {self.deadline_at}, now {now}; refusing "
                "to start work no one will read"
            )
        left = self.remaining(now)
        if estimated_cost > left:
            raise Invalid(
                f"call needs {estimated_cost} but only {left} of the budget "
                "remains; starting it wastes budget a shorter path might use"
            )
        return f"call begins with {left} budget remaining"

    def hop_note(self, now: int) -> str:
        left = self.remaining(now)
        if left <= 0:
            return (
                "no budget left at this hop; the early hops spent the "
                "deadline before the work that needed it, speed them up"
            )
        return f"{left} of the shared deadline budget remains at this hop"
