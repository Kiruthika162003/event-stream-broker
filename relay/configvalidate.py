"""Config validation: the dangerous mistakes live between fields, not in them.

Every topic config field has a valid range, and checking each
field alone catches the typos but misses the mistakes that cause
incidents, because those live in the relationships between fields.
The validator checks the cross-field constraints that a
per-field pass cannot see. Min-insync-replicas must not exceed
the replication factor, because a topic requiring three in-sync
copies on a two-replica topic can never satisfy an acks-all write
and every such produce blocks forever, a config that is valid
field by field and broken as a whole. A compacted topic must have
a finite retention or the compaction and retention interact
strangely, and a topic that is both compacted and size-retained
needs the operator to understand which deletes what. The
retention window must exceed the segment roll time, because
retention deletes whole sealed segments and a window shorter than
the time to seal a segment can never delete anything, so a topic
that looks like it retains an hour actually retains until the
segment fills. The validator reports each violation with the two
fields in tension and the failure it produces, because a
validation error naming one field sends the operator to fix the
wrong thing, while one naming both fields and the consequence
points straight at the real problem. It distinguishes errors,
configs that cannot work, from warnings, configs that work but
surprise, because refusing a surprising-but-valid config is
paternalism while refusing a broken one is the validator's job.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class TopicConfig:
    replication_factor: int
    min_insync_replicas: int
    retention_ticks: int
    segment_roll_ticks: int
    compacted: bool
    size_retained: bool


def validate(config: TopicConfig) -> list[str]:
    errors = []
    if config.min_insync_replicas > config.replication_factor:
        errors.append(
            f"min-insync {config.min_insync_replicas} exceeds "
            f"replication factor {config.replication_factor}: "
            "acks-all writes block forever, valid per field and "
            "broken as a whole"
        )
    if config.retention_ticks <= config.segment_roll_ticks:
        errors.append(
            f"retention {config.retention_ticks} is not longer "
            f"than segment roll {config.segment_roll_ticks}: "
            "retention deletes whole sealed segments, so a window "
            "shorter than the seal time deletes nothing"
        )
    if errors:
        raise Invalid("; ".join(errors))
    return []


def warnings(config: TopicConfig) -> list[str]:
    notes = []
    if config.compacted and config.size_retained:
        notes.append(
            "compacted and size-retained together: the operator "
            "must know which deletes what, a surprise not an error"
        )
    if (
        config.min_insync_replicas == config.replication_factor
        and config.replication_factor > 1
    ):
        notes.append(
            "min-insync equals replication factor: any single "
            "replica loss stops acks-all writes, maximally durable "
            "and minimally available"
        )
    return notes
