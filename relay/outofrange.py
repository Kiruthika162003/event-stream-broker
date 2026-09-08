"""Out of range: a fetch below or above the window, resolved by which way.

A consumer fetches an offset that is not in the log, and the two
directions mean opposite things and need opposite handling. Below
the log start means the consumer's position aged out while it was
away, retention deleted the records it wanted, and the resolution
depends on policy, reset to earliest to read what survives or
error to make the data loss visible, the same choice offset-reset
faces. Above the log end is different and sharper: it means the
consumer thinks the log is longer than it is, which on a healthy
partition is impossible, because a consumer only reaches an offset
by reading up to it, so an offset past the end signals something
wrong, most often that the consumer is talking to a replica that
was truncated after an unclean election and has less log than the
consumer already saw from the old leader. That case must not
silently reset, because resetting hides a real divergence, so the
resolver treats above-the-end as a signal to refresh metadata and
re-find the leader, not as a routine reset. The distinction is the
whole point: below-the-end is the consumer falling behind, a
recoverable and expected condition, while above-the-end is the
log going backward under the consumer, a symptom of truncation or
a stale replica that a reset would paper over. The resolver names
which direction and its cause, because a consumer that resets on
both looks like it is coping while it is actually losing its place
on every unclean failover.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class Window:
    log_start: int
    log_end: int

    def __post_init__(self) -> None:
        if self.log_start > self.log_end:
            raise Invalid("log start cannot exceed log end")

    def contains(self, offset: int) -> bool:
        return self.log_start <= offset < self.log_end


def resolve_out_of_range(
    window: Window, offset: int, reset_policy: str
) -> str:
    if window.contains(offset):
        return f"offset {offset} is in range, fetch proceeds"
    if offset < window.log_start:
        if reset_policy == "earliest":
            return (
                f"below the window: {offset} aged out, reset to "
                f"the log start {window.log_start} and read what "
                "survives"
            )
        return (
            f"below the window: {offset} aged out; the policy is "
            "error, making the data loss visible rather than "
            "silently skipping"
        )
    return (
        f"above the end: {offset} is past the log end "
        f"{window.log_end}, which a healthy partition cannot "
        "reach; refresh metadata and re-find the leader, because "
        "this is truncation or a stale replica, not a routine "
        "reset a silent reset would paper over"
    )
