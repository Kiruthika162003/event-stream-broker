"""Retraction: a late record already emitted a wrong result, so unsay it first.

A windowed aggregate that has emitted a result downstream and then
receives a late record for that window has a problem the suppression
approach sidesteps by waiting: here the result is already out, and a
downstream has acted on it. The fix is a retraction. The operator
emits, for the corrected window, first a retraction of the old
value, a record marked as an undo, and then the new corrected value,
so a downstream that understands retractions subtracts the old and
adds the new, ending at the right total. This lets results be
emitted early, before a window is final, and corrected later as late
records arrive, trading the extra downstream traffic of retractions
for lower latency than waiting for the window to close. The
requirement it puts on the downstream is the catch: a downstream
must understand retractions and process them, subtracting a
retracted value, or it will double-count, treating the retraction
and the correction as two additions rather than an undo and a redo.
So a stream that emits retractions and a downstream that ignores
them is a silent overcount, which is why retraction support is a
contract between producer and consumer of the stream, not a
unilateral choice. The emitter records a window's last emitted
value, and on an update produces a retraction of it followed by the
new value, and it refuses to retract a window that never emitted,
since there is nothing to undo and a spurious retraction would make
a downstream subtract a value it never added. It reports the
retraction count, because a stream emitting many retractions is one
seeing many late records, where suppressing until the window closed
might send less than a retraction per late arrival."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class RetractingEmitter:
    emitted: dict[int, int] = field(default_factory=dict)
    retractions: int = 0

    def emit(self, window: int, value: int) -> list[tuple[str, int, int]]:
        # returns a list of (kind, window, value): "add" or "retract"
        out: list[tuple[str, int, int]] = []
        if window in self.emitted:
            out.append(("retract", window, self.emitted[window]))
            self.retractions += 1
        out.append(("add", window, value))
        self.emitted[window] = value
        return out

    def retract_only(self, window: int) -> tuple[str, int, int]:
        if window not in self.emitted:
            raise Invalid(
                f"window {window} never emitted; a spurious retraction would "
                "make a downstream subtract a value it never added"
            )
        value = self.emitted.pop(window)
        self.retractions += 1
        return ("retract", window, value)

    def net_effect(self, records: list[tuple[str, int, int]]) -> int:
        # what a retraction-aware downstream computes: add minus retract
        total = 0
        for kind, _window, value in records:
            total += value if kind == "add" else -value
        return total

    def report(self) -> str:
        return (
            f"{self.retractions} retraction(s) emitted; a stream emitting many "
            "is seeing many late records, where suppressing until the window "
            "closed might send less than a retraction per late arrival"
        )
