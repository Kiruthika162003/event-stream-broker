"""Branch: split a stream by predicate, first match wins, and order is meaning.

Branching sends each record of a stream to one of several output
streams chosen by predicate, the routing step behind a topology
that treats high-value orders differently from ordinary ones or
routes by region. The rule that makes branching predictable is
first-match: a record is tested against the branches in order and
goes to the first whose predicate it satisfies, not to every
matching branch, so the branches partition the records rather than
duplicating them. This makes the order of the branches part of the
logic, not a detail: a broad predicate placed before a narrow one
captures records the narrow one was meant to get, so the narrow,
specific branches must come first and the broad catch-alls last,
and swapping two branches can silently change which stream a record
lands in. A record matching no branch is not an error but a
decision: it can be dropped, which quietly loses it, or sent to a
default branch, which keeps it for inspection, and the router makes
that choice explicit rather than defaulting to a silent drop, using
an explicit dropped bucket so a lost record is a counted decision
rather than a disappearance. The report states how records distributed
across the branches, because a branch receiving nothing usually has
a predicate a preceding branch already satisfies, the first-match
shadowing that a distribution count reveals and a branch definition
read in isolation hides.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class Brancher:
    branches: list[tuple[str, Callable[[int], bool]]] = field(
        default_factory=list
    )
    default: str | None = None
    counts: dict[str, int] = field(default_factory=dict)

    def route(self, record: int) -> str:
        for name, predicate in self.branches:
            if predicate(record):
                self.counts[name] = self.counts.get(name, 0) + 1
                return name
        if self.default is not None:
            self.counts[self.default] = self.counts.get(self.default, 0) + 1
            return self.default
        self.counts["<dropped>"] = self.counts.get("<dropped>", 0) + 1
        return "<dropped>"

    def distribution(self) -> str:
        parts = ", ".join(
            f"{name}: {n}" for name, n in sorted(self.counts.items())
        )
        return (
            f"{parts}; a branch receiving nothing usually has a "
            "predicate a preceding branch already satisfies, the "
            "first-match shadowing a count reveals"
        )

    def starved(self) -> list[str]:
        return [
            name
            for name, _ in self.branches
            if self.counts.get(name, 0) == 0
        ]
