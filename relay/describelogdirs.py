"""DescribeLogDirs: where the bytes actually sit, per directory and partition.

A broker with several log directories, one per disk, spreads its
partitions across them, and an operator diagnosing a full disk or
an unbalanced broker needs to know not the total size but its
distribution: which directory is filling, which partitions are the
heavy ones, and whether a single partition is dominating a disk.
DescribeLogDirs answers that by reporting, per directory, the size
of each partition replica living there, and the aggregate makes
two facts visible that a single total hides. The first is skew
across directories: two disks at very different utilization mean
the placement put too much on one, and moving a partition to the
emptier disk rebalances it, which the report surfaces as the gap
between the fullest and emptiest directory. The second is a
dominant partition: a single partition holding most of a
directory's bytes cannot be relieved by moving other partitions
off that disk, only by moving that partition itself or shrinking
its retention, so the report names the largest partition per
directory rather than only the directory total. The analyzer
refuses a report for a directory that is marked offline, because a
disk that failed cannot report its sizes and a zero from it would
be read as empty rather than unknown, hiding data that is at risk
rather than gone. The report states the imbalance so a decision to
move a partition is grounded in which disk needs relief and which
partition would relieve it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class LogDir:
    path: str
    partition_sizes: dict[str, int] = field(default_factory=dict)
    offline: bool = False

    def total(self) -> int:
        if self.offline:
            raise Invalid(
                f"log dir {self.path} is offline; its sizes are "
                "unknown, not zero, and its data may be at risk"
            )
        return sum(self.partition_sizes.values())

    def largest_partition(self) -> tuple[str, int]:
        if not self.partition_sizes:
            return ("", 0)
        name = max(self.partition_sizes, key=self.partition_sizes.get)
        return (name, self.partition_sizes[name])


@dataclass
class LogDirsReport:
    dirs: list[LogDir] = field(default_factory=list)

    def imbalance(self) -> str:
        live = [d for d in self.dirs if not d.offline]
        if len(live) < 2:
            return "fewer than two live dirs; nothing to balance"
        totals = {d.path: d.total() for d in live}
        fullest = max(totals, key=totals.get)
        emptiest = min(totals, key=totals.get)
        gap = totals[fullest] - totals[emptiest]
        heavy_name, heavy_size = next(
            d for d in live if d.path == fullest
        ).largest_partition()
        return (
            f"{fullest} is {gap} byte(s) fuller than {emptiest}; "
            f"its largest partition {heavy_name} holds {heavy_size}, "
            "which must move itself to relieve the disk, not other "
            "partitions around it"
        )

    def offline_dirs(self) -> list[str]:
        return [d.path for d in self.dirs if d.offline]
