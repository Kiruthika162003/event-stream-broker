"""Outer join: an unmatched record still emits, but only once it can give up.

An inner windowed join emits a pair only when both sides have a
record for a key within the window, dropping a record whose match
never arrives. An outer join keeps the unmatched record too, emitting
it with a null for the missing side, which matters when the absence
is itself information: an order with no matching shipment is a
problem worth seeing, not a row to drop. The hard part is timing:
the join cannot emit an unmatched left record as soon as it arrives,
because its match might still come within the window, but it also
cannot wait forever, so it waits until the record's window has
closed, meaning the watermark has passed the window's end and no
match can arrive anymore, and only then emits the record with a
null. This is why an outer join needs a watermark and an inner join
needs less: the inner join emits on a match and forgets, while the
outer join must track which records are still waiting and emit them
unmatched when their window closes. A match arriving before the
window closes cancels the pending unmatched emission, turning it
into a normal joined pair. The joiner records an arriving record as
pending a match, emits a joined pair and clears the pending flag on
a match, and on a watermark advance emits every pending record whose
window has closed with a null. It refuses to emit an unmatched
record whose window has not yet closed, the premature emission that
would declare no-match while a match could still arrive, and reports
how many records are still pending, because a growing pending set is
a join whose one side is lagging, so matches keep arriving just
before their windows close, the worst case for outer-join latency."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class OuterJoin:
    window: int
    # key -> (arrival_time, matched)
    pending: dict[str, tuple[int, bool]] = field(default_factory=dict)

    def arrive(self, key: str, time: int) -> None:
        self.pending[key] = (time, False)

    def match(self, key: str) -> str:
        if key not in self.pending:
            raise Invalid(f"no pending record for key '{key}' to match")
        arrival, _ = self.pending[key]
        self.pending[key] = (arrival, True)
        return f"joined pair for '{key}'; the pending unmatched emission is cancelled"

    def window_closed(self, key: str, watermark: int) -> bool:
        if key not in self.pending:
            return False
        arrival, _ = self.pending[key]
        return watermark > arrival + self.window

    def advance(self, watermark: int) -> list[str]:
        emitted = []
        for key in list(self.pending):
            arrival, matched = self.pending[key]
            if not matched and watermark > arrival + self.window:
                emitted.append(key)
                del self.pending[key]
        return emitted  # emitted with a null for the missing side

    def emit_unmatched(self, key: str, watermark: int) -> str:
        if not self.window_closed(key, watermark):
            raise Invalid(
                f"window for '{key}' has not closed; emitting unmatched now "
                "would declare no-match while a match could still arrive"
            )
        del self.pending[key]
        return f"emitted '{key}' with a null; its window closed unmatched"

    def report(self) -> str:
        waiting = sum(1 for _, matched in self.pending.values() if not matched)
        return (
            f"{waiting} record(s) pending a match; a growing set is a join "
            "whose one side lags, matches landing just before windows close, "
            "the worst case for outer-join latency"
        )
