"""OffsetFetch: a missing commit is not offset zero, it is no answer at all.

When a consumer starts it asks the coordinator for the group's
committed offset on each partition it owns, and the answer decides
where it resumes. The subtlety that causes real bugs is the
difference between a committed offset of zero and no committed
offset: zero means the group processed nothing and should start at
the beginning, while no commit means the group never recorded a
position for this partition and the consumer must fall back to its
reset policy, earliest or latest, rather than assume zero. The
coordinator represents no-commit as a sentinel, minus one, and a
consumer that treats the sentinel as an offset would seek to a
nonsensical negative position or, worse, silently clamp it to zero
and reprocess the whole partition when its reset policy said latest.
A partial answer is normal: a group that committed some partitions
but not others, common right after a partition was added to a
subscribed topic, gets real offsets for the committed ones and the
sentinel for the rest, so the consumer resumes the known ones and
resets only the new one. The fetcher refuses to return a committed
offset above the partition's log end, because a commit past the end
is corruption in the offsets log and seeking there would skip
records, and it distinguishes a group it has never heard of from a
group with no commits, since both return sentinels but only the
first is worth logging as possibly the wrong group id. The report
counts committed against reset, because a consumer resetting more
partitions than it resumed usually just joined or just had
partitions added.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid

NO_OFFSET = -1


@dataclass
class OffsetFetchResponse:
    log_ends: dict[str, int]
    committed: dict[str, int] = field(default_factory=dict)

    def commit(self, partition: str, offset: int) -> None:
        end = self.log_ends.get(partition)
        if end is not None and offset > end:
            raise Invalid(
                f"committed offset {offset} for {partition} is past "
                f"its log end {end}; a commit beyond the end is "
                "corruption and seeking there would skip records"
            )
        self.committed[partition] = offset

    def fetch(self, partition: str) -> int:
        return self.committed.get(partition, NO_OFFSET)

    def resume_or_reset(self, partition: str) -> str:
        offset = self.fetch(partition)
        if offset == NO_OFFSET:
            return (
                f"{partition}: no commit; fall back to the reset "
                "policy, not offset zero"
            )
        return f"{partition}: resume at committed offset {offset}"

    def summary(self, owned: list[str]) -> str:
        committed = sum(
            1 for p in owned if self.fetch(p) != NO_OFFSET
        )
        reset = len(owned) - committed
        return (
            f"{committed} partition(s) resume from a commit, {reset} "
            "reset; resetting more than resuming usually means the "
            "consumer just joined or had partitions added"
        )
