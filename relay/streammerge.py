"""Stream merge: combine inputs, and the slowest input sets the merged clock.

Merging several input streams into one interleaves their records
into a single stream, which is straightforward for the records
themselves but subtle for time. The merged stream has a single
notion of how far its time has advanced, its watermark, and that
watermark can only move to the point where every input has been
seen up to, because a record could still arrive on any input with a
timestamp behind the others. So the merged watermark is the minimum
of the inputs' watermarks, not the maximum, and this has a
consequence that surprises people: one slow or stalled input holds
back the merged stream's time even while the other inputs race
ahead, because advancing past the slow input's watermark would risk
declaring a time final that the slow input could still contradict.
A stalled input is worse than a slow one: an input that stops
emitting entirely pins the merged watermark at its last position
forever, so downstream windows never close and results never emit,
a stall that looks like the whole pipeline hung when only one input
died. The merger computes the merged watermark as the input
minimum and names which input is the laggard, because the fix is to
that input, not the merger. It refuses to advance the merged
watermark past the minimum, the correctness rule, and it refuses an
input watermark that goes backwards, since a watermark only ever
advances and a regression is a bug in the input. The report states
the gap between the fastest and slowest input, because a widening
gap is an input falling behind, the early warning before the slow
input becomes the stalled one that freezes the merged clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class StreamMerge:
    watermarks: dict[str, int] = field(default_factory=dict)

    def observe(self, stream: str, watermark: int) -> None:
        prior = self.watermarks.get(stream, watermark)
        if watermark < prior:
            raise Invalid(
                f"input '{stream}' watermark went backwards "
                f"({watermark} < {prior}); a watermark only advances, "
                "a regression is a bug in the input"
            )
        self.watermarks[stream] = watermark

    def merged_watermark(self) -> int:
        if not self.watermarks:
            return 0
        return min(self.watermarks.values())

    def laggard(self) -> str:
        if not self.watermarks:
            raise Invalid("no inputs observed yet")
        return min(self.watermarks, key=self.watermarks.get)

    def spread(self) -> str:
        if not self.watermarks:
            return "no inputs observed"
        fastest = max(self.watermarks.values())
        slowest = min(self.watermarks.values())
        gap = fastest - slowest
        return (
            f"merged watermark {slowest} held by '{self.laggard()}'; "
            f"{gap} behind the fastest input, and a widening gap is the "
            "early warning before a slow input becomes a stalled one "
            "that freezes the merged clock"
        )
