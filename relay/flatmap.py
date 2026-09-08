"""Flat map: one record becomes many, and the fan-out sizes the downstream.

A flat-map transform turns each input record into zero, one, or
many output records: a line of text into its words, an order into
one record per line item, a batch into its elements. This is more
than a map, which is one-to-one, because the count changes, and the
change is the thing to watch: a flat-map with an average fan-out of
ten turns a thousand input records a second into ten thousand
output records a second, so a downstream sized for the input rate
is overwhelmed by the output rate, and the fan-out ratio is exactly
the multiplier the downstream must be sized for. A flat-map that
emits zero for some inputs is also a filter, and one that emits
many is an amplifier, and knowing which a given flat-map is comes
from the ratio, not the code. The processor applies a fan-out
function to each record, collects the outputs, and tracks the input
and output counts so the fan-out ratio is measured rather than
assumed, because a flat-map whose real ratio differs from the
expected one is the surprise behind a downstream that fell over: a
parser that emits more tokens than expected, or a join that
multiplied rows. It refuses a fan-out function that returns
something other than a list, because a flat-map must produce a
collection even when that collection is empty, and a bare value
would be ambiguous between one output and a malformed one. It
reports the measured fan-out ratio, because sizing the downstream
from the code's intended ratio is guessing, while sizing it from
the measured ratio on real data is the number that keeps the
downstream from being buried by an amplification no one counted."
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from relay.errors import Invalid

FanOut = Callable[[int], list[int]]


@dataclass
class FlatMap:
    fan_out: FanOut
    inputs: int = 0
    outputs: int = 0

    def apply(self, record: int) -> list[int]:
        result = self.fan_out(record)
        if not isinstance(result, list):
            raise Invalid(
                "a flat-map must return a list, even an empty one; a bare "
                "value is ambiguous between one output and a malformed one"
            )
        self.inputs += 1
        self.outputs += len(result)
        return result

    def apply_all(self, records: list[int]) -> list[int]:
        out: list[int] = []
        for r in records:
            out.extend(self.apply(r))
        return out

    def fan_out_ratio(self) -> float:
        if self.inputs == 0:
            return 0.0
        return self.outputs / self.inputs

    def report(self) -> str:
        ratio = self.fan_out_ratio()
        kind = "an amplifier" if ratio > 1 else ("a filter" if ratio < 1 else "one-to-one")
        return (
            f"fan-out {ratio:.1f}x ({self.outputs}/{self.inputs}), {kind}; size "
            "the downstream from this measured ratio, not the intended one, "
            "or an amplification no one counted buries it"
        )
