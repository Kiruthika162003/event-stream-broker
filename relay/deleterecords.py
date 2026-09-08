"""Delete records: trim the head on request, but never past what is committed.

Retention deletes old records on a schedule, but sometimes an
operator needs to delete now, to reclaim space urgently or to
honor a deletion request against data known to be consumed. The
delete-records operation advances the log-start offset to a chosen
point, making everything before it unreadable and its segments
reclaimable, and it is more dangerous than retention because it is
manual and immediate, so its guards are stricter. It cannot delete
past the high watermark, because deleting uncommitted records
removes data that was never even promised durable, and while that
loses nothing acknowledged, it desyncs the log-start from reality
in a way that confuses every consumer. More importantly it should
warn when deleting past a live consumer group's committed offset,
because that group has not read the records being deleted, and
while an operator may have a valid reason, deleting unread data is
exactly the mistake the operation makes easy, so the guard makes
it deliberate rather than accidental. The operation is idempotent
in the useful way: deleting up to an offset already below the
log-start is a no-op that succeeds, because an operator retrying a
delete after a timeout should not get an error for work already
done, and it reports the actual records removed versus requested,
because a delete that removed fewer than asked, because some were
already gone, is a success with a smaller number, not a failure,
and conflating the two sends the operator chasing a problem that
does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class LogHead:
    log_start: int
    high_watermark: int

    def __post_init__(self) -> None:
        if self.log_start > self.high_watermark:
            raise Invalid(
                "log start cannot exceed the high watermark"
            )

    def delete_before(
        self,
        target: int,
        committed_offsets: dict[str, int] | None = None,
    ) -> str:
        if target > self.high_watermark:
            raise Invalid(
                f"cannot delete to {target} past the watermark "
                f"{self.high_watermark}; deleting uncommitted "
                "records desyncs the log-start from reality"
            )
        if target <= self.log_start:
            return (
                f"no-op: {target} is already at or below the log "
                f"start {self.log_start}; a retry after a timeout "
                "succeeds, not errors"
            )
        removed = target - self.log_start
        old_start = self.log_start
        self.log_start = target
        warning = ""
        if committed_offsets:
            unread = sorted(
                group
                for group, offset in committed_offsets.items()
                if offset < target
            )
            if unread:
                warning = (
                    f"; WARNING: {unread} have not read past "
                    f"{target}, deleting data they never consumed, "
                    "made deliberate not accidental"
                )
        return (
            f"deleted {removed} record(s) from {old_start} to "
            f"{target}{warning}"
        )
