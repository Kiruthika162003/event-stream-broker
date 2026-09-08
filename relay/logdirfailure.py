"""Log dir failure: one bad disk takes its partitions offline, not the broker.

A broker with several data directories, one per disk in a JBOD
arrangement, spreads its partitions across the disks. When a single
disk fails, the old behavior was to crash the whole broker, which
turned one failed disk into the loss of every partition on that
broker, including the many on disks that were perfectly healthy.
Per-directory failure handling is the better answer: the broker marks
the failed directory offline, takes offline exactly the partitions
that lived on it, and keeps serving every partition on the surviving
directories. The partitions on the dead disk lose their replica on
this broker, so the cluster re-replicates them elsewhere, but the
broker itself stays up and the blast radius is one disk's worth of
partitions rather than all of them. The manager tracks which directory
each partition lives on and which directories are online. Marking a
directory failed moves its partitions to an offline set and leaves the
rest untouched, and a partition on a healthy directory is still
serviceable while one on a failed directory is not. The broker as a
whole is considered down only when every directory has failed, because
a broker with even one working disk can still host the partitions
assigned there. It refuses to place a partition on a directory that is
already failed, because assigning new data to a dead disk is a write
that cannot land, and it refuses to look up a partition it was never
told about. It reports the online and offline directory counts and the
offline partition count, because that is the true blast radius of a
disk failure, the number that per-directory handling exists to keep
small."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid, Missing


@dataclass
class LogDirFailure:
    directories: set[str] = field(default_factory=set)
    failed: set[str] = field(default_factory=set)
    # partition -> directory it lives on
    placement: dict[str, str] = field(default_factory=dict)

    def add_directory(self, directory: str) -> None:
        self.directories.add(directory)

    def place(self, partition: str, directory: str) -> None:
        if directory not in self.directories:
            raise Invalid(f"directory '{directory}' is not known to this broker")
        if directory in self.failed:
            raise Invalid(
                f"directory '{directory}' has failed; assigning new data to a "
                "dead disk is a write that cannot land"
            )
        self.placement[partition] = directory

    def fail(self, directory: str) -> list[str]:
        if directory not in self.directories:
            raise Invalid(f"directory '{directory}' is not known to this broker")
        self.failed.add(directory)
        return sorted(p for p, d in self.placement.items() if d == directory)

    def is_serviceable(self, partition: str) -> bool:
        if partition not in self.placement:
            raise Missing(f"partition '{partition}' was never placed")
        return self.placement[partition] not in self.failed

    def offline_partitions(self) -> list[str]:
        return sorted(
            p for p, d in self.placement.items() if d in self.failed
        )

    def broker_down(self) -> bool:
        # down only when every known directory has failed
        return bool(self.directories) and self.failed >= self.directories

    def note(self) -> str:
        online = len(self.directories) - len(self.failed)
        offline = len(self.offline_partitions())
        return (
            f"{online} online directory/ies, {len(self.failed)} failed, "
            f"{offline} partition(s) offline; that offline count is the blast "
            "radius per-directory handling exists to keep small"
        )
