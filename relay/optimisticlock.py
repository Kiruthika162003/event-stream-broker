"""Optimistic lock: write only if nothing changed since you read, else retry.

Coordinating concurrent writes to one value can be pessimistic,
take a lock before reading so no one else can write until you are
done, or optimistic, do not lock, but check at write time that
nothing changed since you read. Optimistic concurrency suits a
workload where conflicts are rare, because it avoids the lock's
cost on the common uncontended path and pays only when a conflict
actually happens. The mechanism is a version: the value carries a
version number, a writer reads the value and its version, computes
a new value, and writes it with a compare-and-set that succeeds
only if the current version still equals the one it read. If another
writer changed the value in between, the version has moved, the
compare-and-set fails, and the write is rejected as a conflict, so
the writer must re-read the new value and retry its computation on
top of it, not blindly overwrite. This is what makes it safe
without a lock: a write is applied only against the exact state the
writer saw, so a change it did not see cannot be silently clobbered,
the lost-update the LWW register suffers. It maps directly to a
conditional produce, append only if the partition's last offset is
still X, and to a metadata compare-and-set. The lock reads a value
with its version, applies a write only if the version matches, bumps
the version on success, and rejects a stale-version write as a
conflict. It refuses a write whose expected version is not the
current one, naming the conflict, and reports the conflict rate,
because a high rate means contention is not rare after all and the
optimistic bet is wrong, a pessimistic lock would cost less than the
retries."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class OptimisticValue:
    value: int = 0
    version: int = 0
    conflicts: int = 0
    commits: int = 0

    def read(self) -> tuple[int, int]:
        return (self.value, self.version)

    def compare_and_set(self, expected_version: int, new_value: int) -> str:
        if expected_version != self.version:
            self.conflicts += 1
            raise Invalid(
                f"expected version {expected_version} but current is "
                f"{self.version}; another writer changed it, re-read and retry "
                "rather than clobber the change you did not see"
            )
        self.value = new_value
        self.version += 1
        self.commits += 1
        return f"set to {new_value}; version now {self.version}"

    def conflict_rate(self) -> str:
        total = self.conflicts + self.commits
        if total == 0:
            return "no writes yet"
        pct = self.conflicts / total * 100
        return (
            f"{self.conflicts}/{total} writes conflicted ({pct:.0f}%); a high "
            "rate means contention is not rare and the optimistic bet is wrong, "
            "a pessimistic lock would cost less than the retries"
        )
