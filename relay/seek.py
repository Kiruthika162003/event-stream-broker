"""Seek: explicit position control, bounded by what the log actually holds.

A consumer usually advances by committing, but sometimes it must
jump: reprocess from the beginning after a bug fix, skip to the
end after a long outage it cannot afford to replay, or resume at
a specific offset from an external checkpoint. Seek is that
control, and its danger is that it accepts a number the consumer
chose, which may point nowhere valid. Seeking below the log start
lands on data that was already retention-deleted, so it is
clamped to the start with the clamp reported, because silently
starting later than asked would skip records the consumer
intended to read. Seeking past the high watermark points at
uncommitted or nonexistent offsets, so it is clamped to the
watermark, because a consumer positioned past the end would block
forever waiting for records that do not exist yet. Seek to
beginning and seek to end are the two safe named seeks that
cannot be wrong, because they resolve to the log's current bounds
at execution rather than to a number that may have aged out
between the decision and the seek. Every seek reports whether it
landed where asked or was clamped, because a clamped seek that
looks like an exact one is a consumer reading from a different
place than its operator believes.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class LogBounds:
    log_start: int
    high_watermark: int

    def __post_init__(self) -> None:
        if self.log_start > self.high_watermark:
            raise Invalid(
                "log start cannot exceed the high watermark"
            )


def seek_to_offset(
    bounds: LogBounds, requested: int
) -> tuple[int, str]:
    if requested < bounds.log_start:
        return bounds.log_start, (
            f"clamped: {requested} is below the log start "
            f"{bounds.log_start}, aged out; starting later than "
            "asked would skip intended records"
        )
    if requested > bounds.high_watermark:
        return bounds.high_watermark, (
            f"clamped: {requested} is past the watermark "
            f"{bounds.high_watermark}; a consumer positioned "
            "past the end blocks forever on records that do not "
            "exist yet"
        )
    return requested, f"positioned at {requested} as requested"


def seek_to_beginning(bounds: LogBounds) -> tuple[int, str]:
    return bounds.log_start, (
        f"positioned at the log start {bounds.log_start}; a "
        "named seek that resolves at execution and cannot be "
        "stale"
    )


def seek_to_end(bounds: LogBounds) -> tuple[int, str]:
    return bounds.high_watermark, (
        f"positioned at the watermark {bounds.high_watermark}; "
        "resolves to the current end, never a stale number"
    )
