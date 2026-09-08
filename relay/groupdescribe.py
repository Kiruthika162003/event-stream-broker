"""Group describe: the admin view that answers who owns what, and how far behind.

When a consumer group misbehaves, the first question is always the
same: which member owns which partition, and how far behind is
each. The describe view assembles that from the coordinator's
state, one row per partition showing its owner, committed offset,
the partition's end, and the lag between them, because an
operator debugging a slow group needs all four in one place, not
a lag number without the owner that would fix it. The view's
value is in what it surfaces that a single aggregate hides. Total
group lag can look healthy while one partition is catastrophically
behind, because the sum averages the stuck partition against the
fast ones, so the describe view sorts by per-partition lag and
puts the worst first, turning "the group has some lag" into
"partition 7, owned by consumer-3, is 40000 behind while the rest
are current," which names both the symptom and the suspect. It
also surfaces the unowned partition, one assigned to no live
member, which is the invisible failure: its lag grows unbounded
because nobody is reading it, and a group-total lag that includes
it looks like general slowness rather than a specific member that
died without its partition being reassigned. The describe view
refuses to report a group mid-rebalance as if its assignments
were stable, because an ownership snapshot taken during a
reassignment shows partitions in transition as owned by members
about to lose them, a picture that is wrong the instant it is
printed.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class PartitionStatus:
    partition: int
    owner: str | None
    committed: int
    end_offset: int

    def lag(self) -> int:
        return self.end_offset - self.committed


@dataclass
class GroupDescription:
    group: str
    stable: bool
    partitions: list[PartitionStatus]

    def worst_first(self) -> list[PartitionStatus]:
        return sorted(
            self.partitions,
            key=lambda p: (-p.lag(), p.partition),
        )

    def unowned(self) -> list[int]:
        return sorted(
            p.partition for p in self.partitions if p.owner is None
        )

    def describe(self) -> str:
        if not self.stable:
            raise Invalid(
                f"{self.group} is mid-rebalance; an ownership "
                "snapshot now shows partitions owned by members "
                "about to lose them, wrong the instant it prints"
            )
        rows = self.worst_first()
        lines = [f"group {self.group}: {len(rows)} partition(s)"]
        for status in rows:
            owner = status.owner or "UNOWNED"
            lines.append(
                f"  partition {status.partition}: {owner}, "
                f"committed {status.committed}, end "
                f"{status.end_offset}, lag {status.lag()}"
            )
        unowned = self.unowned()
        if unowned:
            lines.append(
                f"  UNOWNED {unowned}: lag grows unbounded, a "
                "member died without reassignment, not general "
                "slowness"
            )
        return "\n".join(lines)
