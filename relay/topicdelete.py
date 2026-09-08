"""Topic deletion: a two-phase retirement, not an instant erase.

Deleting a topic is the most irreversible operation a broker
offers, and doing it in one step is how data vanishes before
anyone confirms it was safe to lose. The retirement is two-phase.
First the topic is marked for deletion: it stops accepting
produces, its metadata records the deletion request with who and
when, but its data stays on disk and its consumers can finish
draining what they were reading. Only after a grace period, and
only when no consumer group still has uncommitted lag against it,
does the second phase actually remove the segments. The gate
between the phases is the consumer check, because deleting a topic
a group is still draining silently truncates that group's work,
and a deletion that races a live consumer is a data-loss bug
disguised as an administrative action. Deletion is also
reversible up until the second phase: a marked-but-not-removed
topic can be un-marked, because the most common reason to delete
a topic is a mistake about which topic, and a retirement that
cannot be cancelled before it destroys anything turns a typo into
an outage. The record of who requested the deletion survives the
removal, because an unattributed deletion is the one audit
question that has no answer when it matters most.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid

ACTIVE = "active"
MARKED = "marked-for-deletion"
REMOVED = "removed"


@dataclass
class TopicLifecycle:
    name: str
    state: str = ACTIVE
    marked_by: str = ""
    marked_at: int = 0
    grace_ticks: int = 100
    audit: list[str] = field(default_factory=list)

    def accepts_produce(self) -> bool:
        return self.state == ACTIVE

    def mark(self, requester: str, now: int) -> str:
        if self.state != ACTIVE:
            raise Invalid(
                f"{self.name} is {self.state}, not active"
            )
        if not requester.strip():
            raise Invalid(
                "a deletion needs a requester; an unattributed "
                "deletion is the audit question with no answer"
            )
        self.state = MARKED
        self.marked_by = requester
        self.marked_at = now
        self.audit.append(f"marked by {requester} at {now}")
        return (
            f"{self.name} marked for deletion by {requester}; "
            "produces stop, data stays, consumers drain"
        )

    def cancel(self) -> str:
        if self.state != MARKED:
            raise Invalid(
                f"{self.name} is {self.state}; only a marked "
                "topic can be un-marked"
            )
        self.state = ACTIVE
        self.audit.append("deletion cancelled")
        return (
            f"{self.name} deletion cancelled; a retirement that "
            "cannot be undone turns a typo into an outage"
        )

    def remove(
        self, now: int, uncommitted_groups: list[str]
    ) -> str:
        if self.state != MARKED:
            raise Invalid("only a marked topic can be removed")
        if now - self.marked_at < self.grace_ticks:
            raise Invalid(
                f"{self.name} is still in its grace period; "
                "removing now would race draining consumers"
            )
        if uncommitted_groups:
            raise Invalid(
                f"{self.name} still has uncommitted lag from "
                f"{sorted(uncommitted_groups)}; removal would "
                "silently truncate their work"
            )
        self.state = REMOVED
        self.audit.append(f"removed at {now}")
        return (
            f"{self.name} removed; the record of who requested "
            f"it ({self.marked_by}) survives the data"
        )
