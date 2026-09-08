"""Window store: values keyed by key and window, kept only while windows live.

A windowed aggregation needs somewhere to hold the running value
for each window of each key, and a plain key-value store is not
enough because the same key has a different value in every window
it spans. The window store keys by the pair of key and window
start, so the count for user A in the nine-o'clock window and the
count for user A in the ten-o'clock window are separate entries,
and a lookup names both the key and the window it wants. The store
is bounded by retention the same way a windowed aggregation is:
windows older than the retention period cannot receive late updates
anymore, so their entries are dropped, which keeps the store from
growing without limit as time advances. This retention is why a
window store is not just a map, it is a map that forgets in window
order, and the retention must be at least the window size plus the
grace period for late records, or a window's entry would be dropped
while records that belong to it could still arrive. The store
supports a range fetch, all windows of a key between two times,
which is how a query reads a key's history across windows, and it
refuses a fetch for a window already expired, distinguishing a key
that never had a value in a window from one whose window aged out,
because the first is a genuine miss and the second is a value that
existed and was retained away. It refuses a retention shorter than
one window, which would expire a window before it closed. The
report states the live window span, because a store whose oldest
live window keeps advancing is healthy while one accumulating
windows faster than retention drops them is a retention set too
long for the update rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid, Missing


@dataclass
class WindowStore:
    window_size: int
    retention: int
    _data: dict[tuple[str, int], int] = field(default_factory=dict)
    _now: int = 0

    def __post_init__(self) -> None:
        if self.retention < self.window_size:
            raise Invalid(
                "retention shorter than one window would expire a window "
                "before it closed"
            )

    def _expire(self) -> None:
        cutoff = self._now - self.retention
        self._data = {
            (k, w): v for (k, w), v in self._data.items() if w >= cutoff
        }

    def put(self, key: str, window: int, value: int, now: int) -> None:
        self._now = max(self._now, now)
        if window < self._now - self.retention:
            raise Invalid(
                f"window {window} is already expired at now {self._now}; "
                "it can no longer receive updates"
            )
        self._data[(key, window)] = value
        self._expire()

    def get(self, key: str, window: int) -> int:
        if (key, window) not in self._data:
            raise Missing(
                f"no live value for '{key}' in window {window}; either "
                "never set or retained away"
            )
        return self._data[(key, window)]

    def fetch_range(self, key: str, low: int, high: int) -> list[tuple[int, int]]:
        return sorted(
            (w, v)
            for (k, w), v in self._data.items()
            if k == key and low <= w <= high
        )

    def live_span(self) -> str:
        windows = [w for _, w in self._data]
        if not windows:
            return "no live windows"
        return (
            f"live windows {min(windows)}..{max(windows)}; an oldest that "
            "keeps advancing is healthy, one accumulating is retention too "
            "long for the update rate"
        )
