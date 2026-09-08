"""Outbox: you cannot commit a database row and a broker write together.

A service that changes its database and publishes an event about
the change wants both to happen or neither, but the database and
the broker are separate systems with no shared transaction, so a
naive service that writes the row then publishes can crash between
the two and leave the row written with no event, or publish then
fail to commit the row and emit an event for a change that did not
happen. The outbox pattern removes the gap by making the publish
part of the database transaction indirectly: the service writes the
event into an outbox table in the same transaction as the business
change, so the two commit atomically in the database, and a
separate relay process reads unpublished outbox rows and publishes
them to the broker, marking each published once the broker
acknowledges. This turns the impossible atomic write across two
systems into two reliable steps: an atomic database commit, then an
at-least-once relay. At-least-once is the honest guarantee, because
the relay can crash after the broker acknowledges but before it
marks the row published, and on restart it republishes that row, so
the consumer must deduplicate, which is why outbox events carry a
stable id. The relay refuses to mark a row published before the
broker has acknowledged it, the gap that would drop an event on a
relay crash, and it publishes rows in insertion order so events for
one entity keep their order. It refuses to publish a row already
marked published, a double-publish beyond the at-least-once the
pattern already allows. The report states the unpublished backlog,
because a growing outbox is a relay that has stalled while the
business kept writing, an event lag invisible until a consumer
notices it is behind.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class OutboxRelay:
    rows: list[tuple[int, str]] = field(default_factory=list)
    published: set[int] = field(default_factory=set)

    def enqueue(self, row_id: int, payload: str) -> None:
        # written in the same DB transaction as the business change
        self.rows.append((row_id, payload))

    def unpublished(self) -> list[tuple[int, str]]:
        return [(rid, p) for rid, p in self.rows if rid not in self.published]

    def publish_next(self, broker_acked: bool) -> str:
        pending = self.unpublished()
        if not pending:
            return "nothing to publish; the outbox is drained"
        row_id, payload = pending[0]
        if not broker_acked:
            raise Invalid(
                f"refusing to mark row {row_id} published before the broker "
                "acknowledged; that gap would drop the event on a relay crash"
            )
        self.published.add(row_id)
        return f"published row {row_id} ('{payload}') in order, then marked it"

    def mark_published(self, row_id: int) -> None:
        if row_id in self.published:
            raise Invalid(
                f"row {row_id} is already published; a double-publish beyond "
                "the at-least-once the pattern allows"
            )
        self.published.add(row_id)

    def backlog(self) -> str:
        n = len(self.unpublished())
        return (
            f"{n} unpublished outbox row(s); a growing backlog is a stalled "
            "relay while the business kept writing, an invisible event lag"
        )
