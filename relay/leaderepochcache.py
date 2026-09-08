"""Leader epoch cache: which offset each leadership term began at.

Every partition leader serves under a leader epoch, a number that
increases each time leadership changes, and the broker records, for
each epoch it led, the offset at which that epoch's records began.
This cache is what lets a follower recover correctly after a
leadership change: instead of blindly trusting its own log, the
follower asks the leader for the end offset of a given epoch, and
where the two disagree it truncates, because a divergence can only
happen at an epoch boundary, never inside a single leader's
continuous run. The cache is a list of epoch and start-offset
pairs kept in increasing order, and the lookup for an epoch returns
the start of the next epoch, the offset one past the last record
that epoch could have written, which is exactly the point a
follower on that epoch must not have gone past. A lookup for the
current epoch returns the log end offset, because the current epoch
has no successor yet and its records run to the end. The cache is
truncated from both ends: when the log start advances, epochs
entirely below it are dropped because their records are gone, and
when a follower truncates its log it drops epoch entries above the
truncation point because those records no longer exist. The cache
refuses an epoch that goes backwards, because a leader epoch only
ever increases, and an out-of-order append would corrupt the very
invariant the cache exists to protect. The report states the epoch
span retained, because a follower asking about an epoch older than
the cache remembers must fall back to truncating to the log start.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid, Missing


@dataclass
class LeaderEpochCache:
    log_end: int = 0
    entries: list[tuple[int, int]] = field(default_factory=list)

    def assign(self, epoch: int, start_offset: int) -> None:
        if self.entries and epoch <= self.entries[-1][0]:
            raise Invalid(
                f"epoch {epoch} does not exceed the last recorded "
                f"epoch {self.entries[-1][0]}; a leader epoch only "
                "ever increases"
            )
        self.entries.append((epoch, start_offset))

    def end_offset_for(self, epoch: int) -> int:
        if not self.entries or epoch < self.entries[0][0]:
            raise Missing(
                f"epoch {epoch} is older than the cache remembers; "
                "the follower must fall back to the log start"
            )
        for idx, (ep, _start) in enumerate(self.entries):
            if ep == epoch:
                if idx + 1 < len(self.entries):
                    return self.entries[idx + 1][1]
                return self.log_end
            if ep > epoch:
                return self.entries[idx][1]
        return self.log_end

    def truncate_from(self, offset: int) -> int:
        before = len(self.entries)
        self.entries = [e for e in self.entries if e[1] < offset]
        self.log_end = min(self.log_end, offset)
        return before - len(self.entries)

    def drop_below(self, log_start: int) -> int:
        before = len(self.entries)
        kept = [e for e in self.entries if e[1] >= log_start]
        if not kept and self.entries:
            kept = [self.entries[-1]]
        self.entries = kept
        return before - len(self.entries)

    def span(self) -> str:
        if not self.entries:
            return "no epochs retained; recovery truncates to the log start"
        return (
            f"epochs {self.entries[0][0]}..{self.entries[-1][0]} "
            f"retained; an older epoch falls back to the log start"
        )
