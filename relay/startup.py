"""Startup: a broker validates every log directory before it serves one.

A broker restarting loads its partitions from log directories on
disk, and the load is where an unclean shutdown's damage is found
and fixed, or missed and served. Each partition directory is
checked: its segments must form a contiguous offset range with no
gap, its last segment must be the only unsealed one, and its
recorded end offset must match the actual last record, because a
mismatch means a write was interrupted and the recovery must
truncate to the last intact record. A directory that fails these
checks is not silently skipped, because a silently skipped
partition is a partition that vanishes from the cluster while its
data sits on disk unserved, so the broker marks it offline and
refuses to lead it until an operator inspects it, trading the
partition's availability for the certainty that the broker never
serves torn data as if it were whole. Startup is all-or-parts,
not all-or-nothing: a broker with one bad directory serves its
other partitions and quarantines the bad one, because refusing to
start over a single damaged partition takes down the healthy ones
with it, and the whole point of many partitions is that one
failing does not fail the rest.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass(frozen=True)
class LogDir:
    partition: int
    segment_bases: tuple[int, ...]
    segment_ends: tuple[int, ...]
    recorded_end: int
    actual_end: int

    def is_contiguous(self) -> bool:
        for base, end in zip(
            self.segment_bases[1:], self.segment_ends[:-1],
            strict=False,
        ):
            if base != end:
                return False
        return True


@dataclass
class BrokerStartup:
    online: list[int] = field(default_factory=list)
    offline: dict[int, str] = field(default_factory=dict)

    def load(self, log_dir: LogDir) -> str:
        if not log_dir.segment_bases:
            self.offline[log_dir.partition] = "no segments"
            return f"partition {log_dir.partition} offline: empty dir"
        if not log_dir.is_contiguous():
            self.offline[log_dir.partition] = (
                "offset gap between segments"
            )
            return (
                f"partition {log_dir.partition} offline: a gap "
                "means a missing segment, quarantined so torn "
                "data is never served as whole"
            )
        if log_dir.recorded_end != log_dir.actual_end:
            self.offline[log_dir.partition] = (
                f"end mismatch: recorded {log_dir.recorded_end}, "
                f"actual {log_dir.actual_end}"
            )
            return (
                f"partition {log_dir.partition} offline: an "
                "interrupted write; recovery must truncate to "
                "the last intact record before it leads"
            )
        self.online.append(log_dir.partition)
        return f"partition {log_dir.partition} online"

    def load_all(self, dirs: list[LogDir]) -> str:
        for log_dir in dirs:
            self.load(log_dir)
        if not self.online and not self.offline:
            raise Invalid("no directories to load")
        return (
            f"{len(self.online)} partition(s) online, "
            f"{len(self.offline)} quarantined; a broker that "
            "refused to start over one bad directory would take "
            "the healthy partitions down with it"
        )
