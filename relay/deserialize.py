"""Deserialize: a record the consumer cannot parse blocks everything behind it.

A consumer deserializes each record before handing it to the
application, and a record that fails to deserialize, a poison pill,
is a problem with no painless answer. The consumer cannot process
it, but it also cannot simply move on without deciding what moving
on means, because the poison pill sits at a specific offset and
everything behind it waits: a consumer that retries the same record
forever makes no progress and its lag grows without bound, stuck on
one bad record while good ones pile up behind it. The three honest
choices are to stop, to skip, or to divert, and each has a named
cost. Stopping surfaces the problem loudly and loses nothing but
halts the partition until a human intervenes. Skipping advances
past the poison pill so the partition drains, but the bad record is
gone unexamined, which is data loss the operator chose, acceptable
for a metric and not for a payment. Diverting sends the bad record
to a dead-letter destination and advances, keeping progress without
losing the record, at the cost of somewhere to put it and something
to look at it later. The handler makes the choice explicit rather
than defaulting, because a consumer that silently skips poison
pills is losing data no one decided to lose, and one that silently
blocks is stalling with no one told why. It refuses to advance the
committed offset past a poison pill under the stop policy, because
committing past a record the consumer never handled is the silent
skip wearing the stop policy's name. The report states how many
poison pills a partition has hit, because a rising count is a
producer writing malformed records upstream, the real bug behind
the symptom.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid

STOP = "stop"
SKIP = "skip"
DIVERT = "divert"


@dataclass
class PoisonHandler:
    policy: str
    committed: int = 0
    diverted: list[int] = field(default_factory=list)
    hits: int = 0

    def __post_init__(self) -> None:
        if self.policy not in (STOP, SKIP, DIVERT):
            raise Invalid(f"unknown poison policy '{self.policy}'")

    def on_poison(self, offset: int) -> str:
        self.hits += 1
        if self.policy == STOP:
            raise Invalid(
                f"poison record at offset {offset}: stopping the "
                "partition; committing past it would be a silent "
                "skip wearing the stop policy's name"
            )
        if self.policy == SKIP:
            self.committed = offset + 1
            return (
                f"skipped offset {offset}: partition drains but the "
                "record is gone unexamined, a loss the operator chose"
            )
        self.diverted.append(offset)
        self.committed = offset + 1
        return (
            f"diverted offset {offset} to the dead-letter and "
            "advanced: progress kept, record not lost"
        )

    def health(self) -> str:
        return (
            f"{self.hits} poison pill(s) hit under '{self.policy}'; a "
            "rising count is a producer writing malformed records "
            "upstream, the bug behind the symptom"
        )
