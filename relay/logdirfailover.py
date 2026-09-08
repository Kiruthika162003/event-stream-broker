"""Log dir failover: one dead disk takes its partitions offline, not the broker.

A broker with several log directories, one per disk, does not lose
everything when one disk fails, because the partitions are spread
across the disks and only the ones on the failed disk are affected.
This is the point of running multiple log dirs, JBOD, over one big
RAID volume: a single disk failure is contained to its share of the
partitions rather than taking the whole broker down. When a disk
fails the broker marks that log dir offline, takes its partitions
offline, and keeps serving every partition on the healthy disks, so
the blast radius of a disk failure is the partitions on that disk,
not the broker. The controller is told which partitions went
offline so it can move their leadership to replicas on other
brokers, restoring their availability elsewhere while this broker
runs on with the rest. The manager marks a dir failed, moves its
partitions to an offline set, and reports the surviving capacity,
and it draws one hard line: if every log dir has failed, the broker
has no working storage at all and shuts down rather than pretending
to serve, because a broker with no healthy disk cannot hold a
single partition and staying up only delays the failover its
shutdown triggers. It refuses to mark a dir failed twice, a
duplicate that would double-count the offline partitions, and
refuses to bring a partition back on a dir still marked failed. The
report states surviving dirs against failed and the count of
offline partitions, because an operator seeing one disk fail needs
to know how many partitions to expect the controller to move, not
just that a disk died.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class LogDirManager:
    dir_partitions: dict[str, set[str]] = field(default_factory=dict)
    failed: set[str] = field(default_factory=set)

    def offline_partitions(self) -> set[str]:
        offline: set[str] = set()
        for d in self.failed:
            offline |= self.dir_partitions.get(d, set())
        return offline

    def fail_dir(self, path: str) -> str:
        if path not in self.dir_partitions:
            raise Invalid(f"unknown log dir '{path}'")
        if path in self.failed:
            raise Invalid(
                f"log dir '{path}' is already failed; a double mark "
                "double-counts the offline partitions"
            )
        self.failed.add(path)
        moved = self.dir_partitions.get(path, set())
        if self.all_failed():
            return (
                f"log dir '{path}' failed; every dir is now down, the "
                "broker has no working storage and shuts down rather than "
                "pretending to serve"
            )
        return (
            f"log dir '{path}' failed, {len(moved)} partition(s) offline; "
            "the broker serves the healthy dirs on"
        )

    def all_failed(self) -> bool:
        return bool(self.dir_partitions) and self.failed == set(self.dir_partitions)

    def surviving_dirs(self) -> list[str]:
        return sorted(set(self.dir_partitions) - self.failed)

    def report(self) -> str:
        return (
            f"{len(self.surviving_dirs())} surviving dir(s), "
            f"{len(self.failed)} failed, {len(self.offline_partitions())} "
            "partition(s) offline for the controller to move"
        )
