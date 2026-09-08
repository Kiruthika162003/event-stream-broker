"""Error budget: an SLO is permission to fail a little, spent at a rate.

A broker fleet running to an availability target does not promise
perfection, it promises a level, and the gap between that level and
perfection is the error budget: the amount of unavailability the
target permits over a window. A target of three-and-a-half nines
over thirty days permits a few hours of downtime, and those hours
are a budget to spend, on risky deploys, on tolerating a flaky
broker before paging, rather than a number to drive to zero at any
cost. The budget reframes two arguments. It ends the debate over
whether to ship a risky change by making it quantitative: if the
budget has room, the change can absorb a failure, and if it is
nearly spent, the change waits. And it distinguishes a slow steady
burn, unavailability trickling within the budget, from a fast burn
that will exhaust the whole window's budget in hours, which is the
one that pages, because the rate of spending, not the total spent,
is what predicts running out. The calculator computes the budget
from the target and window, tracks consumption, and reports the
burn rate as a multiple of the sustainable rate, the rate that
would spend the budget exactly over the window and no faster. It
refuses a target at or above one hundred percent, which is a
promise of perfection with a zero budget that any single failure
breaks, and a target at or below zero, which is no promise at all.
It flags a budget already overspent as a frozen state where risky
changes stop until the window rolls and the budget refills, because
spending a budget already gone is how a minor incident becomes a
major one.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class ErrorBudget:
    target_pct: float
    window_seconds: float
    consumed_seconds: float = 0.0

    def __post_init__(self) -> None:
        if not 0 < self.target_pct < 100:
            raise Invalid(
                "the target must be between 0 and 100 exclusive; 100 is "
                "a zero-budget promise of perfection and 0 is no promise"
            )

    def budget_seconds(self) -> float:
        return self.window_seconds * (100 - self.target_pct) / 100

    def remaining(self) -> float:
        return self.budget_seconds() - self.consumed_seconds

    def is_frozen(self) -> bool:
        return self.remaining() <= 0

    def burn_rate(self, over_seconds: float, spent: float) -> float:
        if over_seconds <= 0:
            raise Invalid("the burn window must be positive")
        sustainable = self.budget_seconds() / self.window_seconds
        actual = spent / over_seconds
        return actual / sustainable if sustainable else float("inf")

    def report(self) -> str:
        if self.is_frozen():
            return (
                f"budget spent ({self.consumed_seconds:.0f}s of "
                f"{self.budget_seconds():.0f}s); frozen, risky changes "
                "wait until the window rolls and it refills"
            )
        return (
            f"{self.remaining():.0f}s of {self.budget_seconds():.0f}s "
            "budget left; room to absorb a failure, so a risky change "
            "can ship"
        )
