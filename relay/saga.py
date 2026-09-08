"""Saga: no distributed transaction, so undo the earlier steps when a later fails.

A business operation that spans several services, reserve
inventory, charge the card, schedule shipping, cannot be one
transaction across their separate databases, so a saga does it as a
sequence of local transactions, each committing in its own service,
and makes the whole thing atomic-ish by defining a compensation for
each step, an action that undoes it. The saga runs the steps
forward, and if a step fails, it does not leave the earlier steps
applied, it runs their compensations in reverse order, releasing the
inventory it reserved and refunding the card it charged, so the
system ends as if the operation never happened, eventually. This is
weaker than a real transaction: there is a window where some steps
are applied and others not, so the intermediate state is visible,
and the compensations must be written to tolerate that a step they
undo may have had visible effects, a refund is not the same as the
charge never happening. But it is what is available across services
with no shared transaction, and it trades that isolation for being
possible at all. The orchestrator records each completed step,
compensates in reverse on a failure, and refuses to compensate a
step that did not complete, since undoing an action never taken is
a bug that could double-undo or corrupt state. It refuses to
continue forward after a failure, because the saga is now unwinding,
and reports whether the saga committed, is compensating, or fully
compensated, because a saga stuck mid-compensation, a compensation
that itself failed, is the hard case needing a human, a compensation
that cannot complete leaving the system in a partial state the saga
was meant to avoid."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid

RUNNING = "running"
COMPENSATING = "compensating"
COMMITTED = "committed"
COMPENSATED = "compensated"


@dataclass
class Saga:
    steps: list[str]
    completed: list[str] = field(default_factory=list)
    compensated: list[str] = field(default_factory=list)
    state: str = RUNNING

    def __post_init__(self) -> None:
        if not self.steps:
            raise Invalid("a saga needs at least one step")

    def complete_step(self, step: str) -> str:
        if self.state != RUNNING:
            raise Invalid(
                f"cannot run '{step}' forward; the saga is {self.state}, "
                "unwinding, not proceeding"
            )
        if step not in self.steps:
            raise Invalid(f"'{step}' is not a step of this saga")
        self.completed.append(step)
        if self.completed == self.steps:
            self.state = COMMITTED
            return "all steps completed; saga committed"
        return f"'{step}' completed"

    def fail(self) -> list[str]:
        self.state = COMPENSATING
        # compensate completed steps in reverse order
        order = list(reversed(self.completed))
        self.compensated = order
        self.state = COMPENSATED
        return order

    def compensate_step(self, step: str) -> str:
        if step not in self.completed:
            raise Invalid(
                f"'{step}' did not complete; compensating an action never "
                "taken could double-undo or corrupt state"
            )
        return f"compensated '{step}'"

    def report(self) -> str:
        if self.state == COMMITTED:
            return "committed; every step applied"
        if self.state == COMPENSATED:
            return (
                f"compensated {len(self.compensated)} step(s) in reverse; the "
                "system ends as if the operation never happened, eventually"
            )
        return f"{self.state}; a compensation that itself fails needs a human"
