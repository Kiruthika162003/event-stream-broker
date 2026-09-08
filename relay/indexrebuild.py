"""Index rebuild: the index is derived data, so a bad one is scanned back.

A segment's offset index is not the source of truth, the log is,
and the index is a derived shortcut that maps a sparse set of
offsets to file positions so a fetch does not scan from the front.
Because it is derived, it can always be rebuilt from the log, and a
broker rebuilds it in two situations a crash creates. The first is
a missing or short index: if the broker died while writing the
active segment, the index may be missing entries for records the
log already has, detectable because the last indexed offset is
behind the log's end, and the fix is to scan the log forward from
the last indexed position, adding an index entry every interval
until the log end. The second is a corrupt index: if the index's
entries are not strictly increasing, a torn write left it
inconsistent, and since a partial index cannot be trusted to be
correct anywhere the safe response is to discard it entirely and
rebuild from an empty index by scanning the whole segment. The
rebuilder never trusts a suspect index over the log, because the
log is what actually holds the records and the index only claims
where they are, so a disagreement is always resolved in the log's
favor. It refuses to rebuild against a log end below the last
indexed offset, because an index pointing past the log means the
log was truncated under the index and the caller must truncate the
index to the log first, not extend a scan past data that is gone.
The report states how many entries the rebuild produced against the
log length, because an index far smaller than the interval implies
means the scan stopped early on a torn record, itself a sign the
log tail needs recovery before the index is trusted.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class IndexRebuilder:
    interval: int
    log_end: int
    entries: list[tuple[int, int]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.interval < 1:
            raise Invalid("the index interval must be positive")

    def is_corrupt(self) -> bool:
        for i in range(1, len(self.entries)):
            if self.entries[i][0] <= self.entries[i - 1][0]:
                return True
        return False

    def is_short(self) -> bool:
        last = self.entries[-1][0] if self.entries else -1
        return last < self.log_end - 1

    def rebuild(self, positions: dict[int, int]) -> str:
        last_indexed = self.entries[-1][0] if self.entries else -1
        if self.log_end - 1 < last_indexed:
            raise Invalid(
                "the log end is below the last indexed offset; the log "
                "was truncated under the index, so truncate the index to "
                "the log before scanning, not extend past gone data"
            )
        if self.is_corrupt():
            self.entries = []
            start = 0
        else:
            start = last_indexed + 1
        rebuilt = list(self.entries)
        for offset in range(start, self.log_end):
            if offset % self.interval == 0 and offset in positions:
                rebuilt.append((offset, positions[offset]))
        self.entries = rebuilt
        return f"rebuilt to {len(self.entries)} entry(ies) up to log end {self.log_end}"

    def report(self) -> str:
        expected = max(1, self.log_end // self.interval)
        return (
            f"{len(self.entries)} index entry(ies) for a log of "
            f"{self.log_end}; far below the ~{expected} the interval "
            "implies means the scan stopped early on a torn record"
        )
