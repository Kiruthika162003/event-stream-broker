"""Dedup store: remember what was processed, but only for as long as it can recur.

At-least-once delivery means a consumer can see the same record
twice, on a retry or after a rebalance replays uncommitted offsets,
so a consumer that must act on each record exactly once, charge a
card, send an email, needs to recognize a repeat and skip it. It
does that by remembering an idempotency key per record, the record
id or a business key, and dropping any record whose key it has
already processed. The memory cannot be unbounded: remembering
every key forever would grow without limit, so the store keeps keys
only for a deduplication window, long enough to cover the longest
delay a duplicate could arrive after the original, typically the
retry and replay horizon, and expires keys older than that. This is
the honest tradeoff: a duplicate arriving after the window has
expired its key will not be recognized and will be processed again,
so the window must be at least as long as the largest gap between a
record and its possible duplicate, and setting it shorter to save
memory reintroduces the double-processing the store exists to
prevent. The store refuses a non-positive window, which would
expire every key immediately and dedup nothing, and it reports the
key count against time so an operator sees the memory the window
costs. A first sighting of a key is processed and remembered; a
repeat within the window is dropped; a repeat after the window is a
missed duplicate the report surfaces as processed-again, because a
rising count of those means the window is shorter than the actual
duplicate delay and is quietly letting doubles through.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class DedupStore:
    window: int
    seen: dict[str, int] = field(default_factory=dict)
    processed_again: int = 0

    def __post_init__(self) -> None:
        if self.window < 1:
            raise Invalid(
                "the dedup window must be positive; zero expires every "
                "key at once and dedups nothing"
            )

    def _expire(self, now: int) -> None:
        self.seen = {
            key: t for key, t in self.seen.items() if now - t < self.window
        }

    def process(self, key: str, now: int) -> str:
        self._expire(now)
        if key in self.seen:
            return f"duplicate '{key}' dropped, seen at {self.seen[key]}"
        self.seen[key] = now
        return f"processed '{key}' for the first time"

    def note_missed_duplicate(self) -> None:
        self.processed_again += 1

    def report(self, now: int) -> str:
        self._expire(now)
        return (
            f"{len(self.seen)} key(s) remembered over a window of "
            f"{self.window}; {self.processed_again} duplicate(s) arrived "
            "after their key expired and were processed again, a rising "
            "count meaning the window is shorter than the duplicate delay"
        )
