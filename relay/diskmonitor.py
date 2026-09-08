"""Disk monitor: a broker out of disk stops writing, so predict it early.

A broker's disk filling is the failure that turns a healthy
cluster unhealthy in a way retention alone cannot prevent,
because retention frees space at the tail while ingest consumes
it at the head, and if ingest outpaces retention the disk fills
regardless of policy. The monitor tracks free space and the net
fill rate, ingest minus retention reclaim, and projects when the
disk hits the threshold at which the broker must stop accepting
writes to protect itself. The projection is the operational
number, because "disk 78 percent full" is a status while "disk
fills in 6 hours at the current net rate" is a decision, add
capacity, tighten retention, or shed a topic, made with time to
spare rather than during the incident. The monitor also
distinguishes a full disk that is retention working, the tail
being deleted as fast as the head grows, holding steady near a
high mark, from a full disk that is retention losing, the mark
climbing, because the first is a broker sized exactly right and
the second is a broker about to stop, and a status page showing
only the percentage cannot tell them apart. When projected time
to full drops below the lead time an operator needs to react,
the monitor escalates from informational to actionable, because
a warning that arrives after the time to act on it is not a
warning, it is a post-mortem.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class DiskMonitor:
    total_bytes: int
    stop_write_ratio: float
    lead_time: int
    samples: list[tuple[int, int]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not 0 < self.stop_write_ratio <= 1:
            raise Invalid("the stop-write ratio is a fraction")

    def observe(self, tick: int, used_bytes: int) -> None:
        if used_bytes > self.total_bytes:
            raise Invalid("used cannot exceed total")
        if self.samples and tick <= self.samples[-1][0]:
            raise Invalid("samples must advance in time")
        self.samples.append((tick, used_bytes))

    def net_fill_rate(self) -> float:
        if len(self.samples) < 2:
            raise Invalid("a rate needs two samples")
        (t0, u0), (t1, u1) = self.samples[0], self.samples[-1]
        return (u1 - u0) / (t1 - t0)

    def ticks_to_stop(self) -> str:
        rate = self.net_fill_rate()
        used = self.samples[-1][1]
        stop_at = int(self.total_bytes * self.stop_write_ratio)
        if rate <= 0:
            if used >= stop_at:
                return (
                    "at the stop mark but holding steady; "
                    "retention is working, the broker is sized "
                    "right"
                )
            return "free space is stable or growing; no projection needed"
        remaining = stop_at - used
        if remaining <= 0:
            return "already at the stop-write mark; writes halting now"
        ticks = int(remaining / rate)
        verb = (
            "ACTIONABLE"
            if ticks < self.lead_time
            else "informational"
        )
        return (
            f"{verb}: disk hits the stop-write mark in about "
            f"{ticks} tick(s) at the current net fill rate; a "
            "decision made with time to spare, not during the "
            "incident"
        )
