"""Mirroring: copying a topic to another cluster without lying about offsets.

Disaster recovery and geo-locality both want a topic's records
copied to a second cluster, and the naive copy has one fatal
flaw: the destination cluster assigns its own offsets, so a
record that was offset 5000 on the source becomes offset 200 on
the mirror, and a consumer that fails over from source to mirror
resumes at the wrong place, either replaying or skipping. The
mirror maintains an offset translation table, source offset to
destination offset, so a consumer's committed position can be
translated across the failover and it resumes where it left off
in meaning, not in number. The lag is honest: mirroring is
asynchronous by nature, so the mirror always trails, and the
report states the trailing offset because a mirror believed to
be current when it trails by an hour is a disaster recovery
plan that loses an hour and calls it zero. Records are copied
in order per partition, because a mirror that reorders has
broken the one guarantee the source made.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid, Missing


@dataclass
class MirrorLink:
    source_topic: str
    dest_topic: str
    translation: dict[int, int] = field(default_factory=dict)
    dest_next_offset: int = 0
    last_source_copied: int = -1

    def copy(self, source_offset: int) -> int:
        if source_offset <= self.last_source_copied:
            raise Invalid(
                f"source offset {source_offset} is not after "
                f"the last copied {self.last_source_copied}; a "
                "mirror that reorders broke the source's only "
                "guarantee"
            )
        if source_offset != self.last_source_copied + 1:
            raise Invalid(
                f"gap: expected source offset "
                f"{self.last_source_copied + 1}, got "
                f"{source_offset}; a mirror with holes is not a "
                "mirror"
            )
        dest = self.dest_next_offset
        self.translation[source_offset] = dest
        self.dest_next_offset += 1
        self.last_source_copied = source_offset
        return dest

    def translate(self, source_offset: int) -> int:
        dest = self.translation.get(source_offset)
        if dest is None:
            raise Missing(
                f"source offset {source_offset} has not been "
                "mirrored yet; failing over to it would skip "
                "unmirrored records"
            )
        return dest

    def lag(self, source_end: int) -> int:
        return source_end - (self.last_source_copied + 1)

    def status(self, source_end: int) -> str:
        behind = self.lag(source_end)
        if behind == 0:
            return (
                f"{self.dest_topic} is caught up to the source "
                "at this instant, which async mirroring cannot "
                "promise for the next one"
            )
        return (
            f"{self.dest_topic} trails by {behind} record(s); a "
            "mirror believed current when it trails is a DR "
            "plan that loses that gap and calls it zero"
        )
