"""File handles: every open segment costs descriptors, and the OS caps them.

A broker holds a lot of files open at once, and the operating
system limits how many file descriptors a process may have, so a
broker with enough partitions and segments can hit that limit and
then fail to open a new segment or accept a new connection, an
outage that looks mysterious until the descriptor count is checked.
The arithmetic is direct: each open segment is not one file but
three, the log, the offset index, and the time index, so a
partition with several segments open holds several times three
descriptors, and across many partitions that multiplies quickly.
Client and inter-broker connections each cost a descriptor too, so
the total is the segments times their files plus the connections,
against a fixed ceiling the operator set with the OS ulimit. The
danger is that the two consumers of descriptors, segments and
connections, grow independently: a broker sized for its partitions
can still run out when a connection storm arrives, or a broker with
few connections can run out when a retention misconfiguration keeps
too many old segments open. The calculator sums the descriptors
from segments and connections, compares against the limit, and
flags a broker approaching it before it hits, because a broker at
the limit cannot even open the segment it needs to keep serving.
It refuses a files-per-segment below one, since a segment is at
least its log, and reports the headroom, because the fix differs by
which consumer dominates: too many segments points at retention or
segment sizing while too many connections points at the connection
quota, and the breakdown says which to reach for before the broker
runs out of the descriptors it needs to recover.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class FileHandleBudget:
    limit: int
    open_segments: int
    files_per_segment: int = 3
    connections: int = 0

    def __post_init__(self) -> None:
        if self.files_per_segment < 1:
            raise Invalid("a segment is at least its log, one file")
        if self.limit < 1:
            raise Invalid("the descriptor limit must be positive")

    def segment_fds(self) -> int:
        return self.open_segments * self.files_per_segment

    def total(self) -> int:
        return self.segment_fds() + self.connections

    def headroom(self) -> int:
        return self.limit - self.total()

    def at_risk(self, warn_fraction: float = 0.9) -> bool:
        return self.total() >= self.limit * warn_fraction

    def report(self) -> str:
        if self.total() >= self.limit:
            return (
                f"OVER: {self.total()} of {self.limit} descriptors; the "
                "broker cannot open a new segment or accept a connection, "
                "an outage"
            )
        dominant = "segments" if self.segment_fds() >= self.connections else "connections"
        fix = (
            "retention or segment sizing"
            if dominant == "segments"
            else "the connection quota"
        )
        state = "AT RISK" if self.at_risk() else "ok"
        return (
            f"{state}: {self.total()}/{self.limit}, {self.headroom()} "
            f"headroom; {dominant} dominate, reach for {fix}"
        )
