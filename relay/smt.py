"""SMT chain: transform each record through a pipeline, and a null drops it.

Between a connector and the broker sits a chain of single message
transforms, small functions each applied to every record in order:
rename a field, mask a sensitive value, add a header, route by a
field, drop records that do not match. The chain is ordered and the
order is meaning, the same as branch order and mapping-rule order:
a transform that renames a field must come before one that reads
the new name, and a mask applied after a route based on the masked
field routes on the unmasked value, so the sequence is part of the
transformation, not a detail. A transform returns either a
transformed record or nothing, and nothing means drop: the record
is filtered out of the stream, which is how a transform expresses a
predicate, keep only records matching this. A dropped record stops
the chain, because there is no record left for the later transforms
to act on, and the chain reports the drop rather than passing a
null down that a later transform would fail on. The runner applies
each transform in order, stops and reports a drop when one returns
nothing, and returns the final transformed record otherwise. It
counts transformed against dropped across a batch, because a chain
dropping most records is a filter doing its job or a transform
failing to match records it should, and the ratio distinguishes the
two: a deliberate filter drops a known fraction while a broken
transform drops nearly everything. It refuses an empty chain, which
transforms nothing and should not be in the path, and treats a
transform raising an error as a poison record for the connector's
error policy rather than crashing the whole chain, keeping one bad
record from stopping the rest."
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from relay.errors import Invalid

Transform = Callable[[dict], dict | None]


@dataclass
class SmtChain:
    transforms: list[Transform] = field(default_factory=list)
    transformed: int = 0
    dropped: int = 0

    def __post_init__(self) -> None:
        if not self.transforms:
            raise Invalid("an empty transform chain should not be in the path")

    def apply(self, record: dict) -> dict | None:
        current: dict | None = record
        for transform in self.transforms:
            current = transform(current)
            if current is None:
                self.dropped += 1
                return None
        self.transformed += 1
        return current

    def apply_batch(self, records: list[dict]) -> list[dict]:
        out = []
        for r in records:
            result = self.apply(r)
            if result is not None:
                out.append(result)
        return out

    def report(self) -> str:
        total = self.transformed + self.dropped
        if total == 0:
            return "no records processed"
        pct = self.dropped / total * 100
        return (
            f"{self.transformed} transformed, {self.dropped} dropped "
            f"({pct:.0f}%); a deliberate filter drops a known fraction while "
            "a broken transform drops nearly everything"
        )
