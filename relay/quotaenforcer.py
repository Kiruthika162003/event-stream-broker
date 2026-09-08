"""Quota enforcer: throttle a client by delaying it back to its allowed rate.

A shared broker has to stop one loud client from starving the rest,
and the tool is a byte-rate quota, a ceiling on bytes per second per
client. The subtle part is what to do when a client exceeds it.
Rejecting the request is harsh and wastes the work already done to
receive it. The gentler answer is to delay the response: accept the
bytes, then hold the acknowledgment for exactly long enough that the
client's average rate over the measurement window comes back down to
the quota. The delay follows directly from the numbers. Over a window
of some seconds the client is allowed quota times window bytes. If it
actually sent more, the excess divided by the quota is the additional
time the window would have needed to carry those bytes at the allowed
rate, and that is the delay to impose. A client exactly at its quota
waits zero, a client at twice its quota over the window waits one
whole window, and the delay scales smoothly in between, so a client
that keeps pushing is paced to its ceiling rather than cut off. The
enforcer records bytes into the current window, computes the throttle
delay from the overage, and rolls the window forward when it expires,
carrying nothing across so each window is measured on its own. It
refuses a non-positive quota or window, because a zero quota would
demand an infinite delay and a zero window has no rate to measure. It
reports the current window's rate against the quota, because a client
consistently pinned at its quota is one to consider giving more, and a
client always far under is one whose quota could be lent elsewhere."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class QuotaEnforcer:
    quota_bytes_per_sec: float
    window_seconds: float = 1.0
    _window_start: float = 0.0
    _bytes_in_window: int = field(default=0)

    def __post_init__(self) -> None:
        if self.quota_bytes_per_sec <= 0:
            raise Invalid("quota must be positive; a zero quota demands infinite delay")
        if self.window_seconds <= 0:
            raise Invalid("window must be positive; a zero window has no rate")

    def record(self, now: float, byte_count: int) -> float:
        if now >= self._window_start + self.window_seconds:
            # the window expired; start a fresh one carrying nothing across
            self._window_start = now
            self._bytes_in_window = 0
        self._bytes_in_window += byte_count
        return self._throttle_delay()

    def _throttle_delay(self) -> float:
        allowed = self.quota_bytes_per_sec * self.window_seconds
        if self._bytes_in_window <= allowed:
            return 0.0
        overage = self._bytes_in_window - allowed
        # the extra time the window would need to carry the overage at quota
        return overage / self.quota_bytes_per_sec

    def rate(self) -> float:
        return self._bytes_in_window / self.window_seconds

    def note(self) -> str:
        pct = self.rate() / self.quota_bytes_per_sec * 100
        return (
            f"window at {self.rate():.0f} B/s, {pct:.0f}% of quota; a client "
            "pinned at quota is one to consider giving more, one always far "
            "under has quota to lend elsewhere"
        )
