"""Phi accrual: suspect a node gradually, adapting to how it normally beats.

A hard heartbeat timeout makes a binary, brittle call: a node that
misses the timeout by a millisecond is declared dead exactly like
one silent for an hour, and the timeout must be set conservatively
long to avoid false positives, which makes real failures slow to
detect. A phi accrual detector replaces the binary call with a
continuous suspicion level, phi, that rises the longer a heartbeat
is overdue, measured against how regularly the node has beaten
before. A node that heartbeats every second and is now three
seconds silent is far more suspicious than one that beats erratically
every few seconds and is three seconds silent, and phi captures that
by scaling the overdue time by the node's own observed interval, so
the detector adapts to each node rather than applying one timeout to
all. The application then chooses a phi threshold as a suspicion it
is willing to act on, and different actions can use different
thresholds off the same detector, a low phi to stop routing new
work to a node and a higher phi to fail it over, where a single
timeout forces one decision. The detector records heartbeat arrivals
to learn the mean interval, computes phi from the time since the
last heartbeat against that mean, and rises smoothly rather than
stepping. It refuses to compute phi before it has seen any
heartbeat, since it has no interval to judge against, and it treats
a node that has beaten regularly and is now barely overdue as low
phi, not suspicious, avoiding the false positive a tight timeout
would raise. It reports phi against the threshold, because a node
whose phi is climbing steadily is one going quiet, caught while the
suspicion builds rather than at a cliff."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class PhiAccrual:
    threshold: float
    mean_interval: float = 0.0
    last_beat: int = -1
    _beats: int = 0

    def __post_init__(self) -> None:
        if self.threshold <= 0:
            raise Invalid("the phi threshold must be positive")

    def heartbeat(self, now: int) -> None:
        if self.last_beat >= 0:
            interval = now - self.last_beat
            # running mean of observed intervals
            self._beats += 1
            self.mean_interval += (interval - self.mean_interval) / self._beats
        else:
            self._beats = 0
        self.last_beat = now

    def phi(self, now: int) -> float:
        if self.last_beat < 0 or self.mean_interval <= 0:
            raise Invalid(
                "no interval learned yet; phi needs at least two heartbeats "
                "to judge against"
            )
        elapsed = now - self.last_beat
        # a simple monotonic accrual: overdue time in units of the mean
        return elapsed / self.mean_interval

    def is_suspect(self, now: int) -> bool:
        return self.phi(now) >= self.threshold

    def report(self, now: int) -> str:
        p = self.phi(now)
        state = "SUSPECT" if p >= self.threshold else "alive"
        return (
            f"phi {p:.1f} against threshold {self.threshold} ({state}); a phi "
            "climbing steadily is a node going quiet, caught as suspicion "
            "builds rather than at a cliff"
        )
