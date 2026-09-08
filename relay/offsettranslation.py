"""Offset translation: the same record has different offsets on two clusters.

When a topic is mirrored from one cluster to another, a record's
offset does not carry across: the record at offset one thousand on
the source may be at offset four hundred on the target, because the
target's copy of the topic started at a different point and its
offsets count from there. This breaks the obvious failover plan, a
consumer that was at offset one thousand on the source cannot just
resume at offset one thousand on the target, because that offset
points at a different record or none at all. Offset translation
fixes it with a checkpoint stream: the mirror periodically records
pairs of source-offset and the target-offset of the same record, so
a consumer failing over looks up its last source offset in the
checkpoints and resumes at the corresponding target offset. The
translation is approximate between checkpoints, so a consumer
translates to the target offset of the nearest checkpoint at or
before its source offset and may reprocess the few records between
that checkpoint and where it actually was, which is at-least-once
across the failover, the honest guarantee mirroring provides. The
translator finds the floor checkpoint for a source offset and
refuses to translate an offset below the earliest checkpoint,
because the mirror has no mapping that old and the consumer must
reset on the target rather than resume at a guessed offset. It
refuses checkpoints that are not monotonic in both offsets, since
mirroring preserves order and a non-monotonic checkpoint is
corruption in the checkpoint stream. It reports the reprocessing a
translation implies, the gap between the consumer's source offset
and its checkpoint, because a consumer failing over needs to know
how many records it will see again, not discover the duplicates
after the cutover.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid, Missing


@dataclass
class OffsetTranslator:
    checkpoints: list[tuple[int, int]] = field(default_factory=list)

    def add_checkpoint(self, source_offset: int, target_offset: int) -> None:
        if self.checkpoints:
            last_src, last_tgt = self.checkpoints[-1]
            if source_offset <= last_src or target_offset <= last_tgt:
                raise Invalid(
                    "checkpoints must increase in both offsets; mirroring "
                    "preserves order, so a non-monotonic one is corruption"
                )
        self.checkpoints.append((source_offset, target_offset))

    def translate(self, source_offset: int) -> int:
        if not self.checkpoints or source_offset < self.checkpoints[0][0]:
            raise Missing(
                f"source offset {source_offset} predates the earliest "
                "checkpoint; the mirror has no mapping that old, reset on "
                "the target rather than resume at a guess"
            )
        target = self.checkpoints[0][1]
        for src, tgt in self.checkpoints:
            if src <= source_offset:
                target = tgt
            else:
                break
        return target

    def reprocessing(self, source_offset: int) -> str:
        for src, _ in reversed(self.checkpoints):
            if src <= source_offset:
                gap = source_offset - src
                return (
                    f"translating from checkpoint at source {src} reprocesses "
                    f"{gap} record(s); at-least-once across the failover"
                )
        raise Missing("no checkpoint at or before that offset")
