"""Altering config: some changes are instant, some reshape the past.

Changing a topic's config on a running topic looks uniform, one
API call per setting, but the settings differ enormously in what
the change actually does, and treating them alike is how a routine
config change becomes an incident. Some changes are purely
forward-looking and instant: raising the max message size affects
only future produces, lowering retention affects only future
deletion decisions, and these apply cleanly with no effect on
existing data. Some changes reshape the past: switching a topic to
compacted means the existing log will be compacted, collapsing
history that consumers may have expected to replay in full, and
that is not a config tweak, it is a data transformation the
operator must intend. And some changes are unsafe on a live topic
at all: reducing the partition count cannot be done because it
breaks keying, as partition planning already establishes. The
classifier sorts a proposed change into instant, reshaping, or
forbidden, and for reshaping changes it requires an explicit
acknowledgement that existing data will be transformed, because a
compaction switch applied casually can collapse a log a consumer
was about to replay, losing intermediate values that were the
whole point of reading it. The classifier names the category and,
for reshaping and forbidden changes, exactly what they touch,
because an operator who thinks they are tweaking a knob deserves
to know when they are actually rewriting history or attempting the
impossible.
"""

from __future__ import annotations

from relay.errors import Invalid

INSTANT = {"max_message_bytes", "retention_ticks", "max_open_ticks"}
RESHAPING = {"compacted"}
FORBIDDEN = {"partition_count"}


def classify_change(setting: str, acknowledged: bool = False) -> str:
    if setting in INSTANT:
        return (
            f"instant: {setting} affects only future records, "
            "applies cleanly with no effect on existing data"
        )
    if setting in RESHAPING:
        if not acknowledged:
            raise Invalid(
                f"reshaping: changing {setting} transforms "
                "existing data, collapsing history a consumer may "
                "replay; requires an explicit acknowledgement, not "
                "a casual tweak"
            )
        return (
            f"reshaping acknowledged: {setting} will transform "
            "the existing log, intended"
        )
    if setting in FORBIDDEN:
        raise Invalid(
            f"forbidden: {setting} cannot change on a live topic; "
            "reducing it breaks keying, and increasing it needs a "
            "new topic and migration"
        )
    raise Invalid(f"unknown setting {setting}")


def is_safe_live(setting: str) -> bool:
    return setting in INSTANT
