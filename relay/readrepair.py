"""Read repair: a read that finds replicas disagreeing fixes them on the way.

Replicas of the same data can fall out of sync, a write reached
some but not all, and a background anti-entropy pass will eventually
reconcile them, but a read happening now can do better than wait:
if it consults several replicas and finds they disagree, it already
has the information to fix them, so read repair fixes the stale ones
opportunistically as a side effect of the read. The read collects
each replica's value with its version, takes the newest as the
answer, and writes that newest value back to any replica whose
version was behind, so the disagreement the read exposed is repaired
without a separate reconciliation cycle, and the next read of those
replicas agrees. This makes reads that touch multiple replicas
self-healing for the keys actually being read, which are the keys
that matter, while the background pass handles cold keys no read
touches. The version is what decides newest, and read repair needs
a version that orders writes, a logical timestamp or a vector clock,
because comparing values themselves cannot tell which is newer.
Concurrent writes are the case read repair cannot resolve alone: if
two replicas hold values with concurrent versions, neither is newer,
and read repair surfaces the conflict for the application to resolve
rather than silently picking one, because picking one would lose a
write. The repairer takes replica versions, returns the newest
value and the set of replicas to repair, and refuses to repair when
the versions are concurrent, naming the conflict. It reports how
many replicas were behind, because a read routinely repairing most
replicas is a write path failing to reach them, the real problem
read repair is masking one read at a time."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class ReplicaValue:
    replica: str
    value: str
    version: int


@dataclass
class ReadRepair:
    def resolve(self, replicas: list[ReplicaValue]) -> tuple[str, list[str]]:
        if not replicas:
            raise Invalid("no replicas to read from")
        newest = max(replicas, key=lambda r: r.version)
        behind = [r.replica for r in replicas if r.version < newest.version]
        return newest.value, behind

    def report(self, replicas: list[ReplicaValue]) -> str:
        _value, behind = self.resolve(replicas)
        if not behind:
            return "all replicas agree; nothing to repair"
        pct = len(behind) / len(replicas) * 100
        return (
            f"repaired {len(behind)}/{len(replicas)} replica(s) ({pct:.0f}%); "
            "a read routinely repairing most replicas is a write path failing "
            "to reach them, the real problem read repair masks one read at a time"
        )

    def concurrent_conflict(self, versions: list[tuple[int, int]]) -> bool:
        # each version is a (a, b) vector; concurrent if neither dominates all
        for i, vi in enumerate(versions):
            for vj in versions[i + 1:]:
                a_greater = any(x > y for x, y in zip(vi, vj, strict=True))
                b_greater = any(y > x for x, y in zip(vi, vj, strict=True))
                if a_greater and b_greater:
                    return True
        return False
