"""The dead letter queue: the poison record steps aside so the line moves.

A consumer that cannot process a record has two bad options and
one good one. It can crash and retry forever, blocking the
partition behind a record that will never succeed, the poison
pill that halts a whole stream over one malformed event. It can
skip silently, which loses data and hides the bug. Or it can
route the record to a dead letter queue after a bounded number
of attempts, recording why it failed and where it came from,
so the partition advances and the failure becomes a ticket
instead of an outage. The routing is disciplined: a record goes
to the dead letter only after exhausting its retry budget, and
the dead letter entry carries the original topic, partition,
offset, and the exception, because a dead letter without
provenance is a landfill and a dead letter with it is a work
queue. Replay is first-class: a fixed consumer can drain the
dead letter back to the source, because most poison is poison
until the bug is fixed and then it is just data that was early.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass(frozen=True)
class DeadLetter:
    source_topic: str
    source_partition: int
    source_offset: int
    attempts: int
    reason: str


@dataclass
class RetryTracker:
    max_attempts: int
    attempts: dict[tuple[str, int, int], int] = field(
        default_factory=dict
    )
    dead_letters: list[DeadLetter] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise Invalid(
                "max attempts must be at least one; zero means "
                "never try, which is not a retry policy"
            )

    def record_failure(
        self,
        topic: str,
        partition: int,
        offset: int,
        reason: str,
    ) -> str:
        key = (topic, partition, offset)
        count = self.attempts.get(key, 0) + 1
        self.attempts[key] = count
        if count >= self.max_attempts:
            self.dead_letters.append(
                DeadLetter(
                    source_topic=topic,
                    source_partition=partition,
                    source_offset=offset,
                    attempts=count,
                    reason=reason,
                )
            )
            del self.attempts[key]
            return (
                f"offset {offset} dead-lettered after {count} "
                f"attempt(s): {reason}; the partition advances "
                "and the failure is a ticket, not an outage"
            )
        return (
            f"offset {offset} failed attempt {count} of "
            f"{self.max_attempts}: {reason}; will retry"
        )

    def record_success(
        self, topic: str, partition: int, offset: int
    ) -> None:
        self.attempts.pop((topic, partition, offset), None)

    def replay(self, index: int) -> DeadLetter:
        if not 0 <= index < len(self.dead_letters):
            raise Invalid(
                "no dead letter at that position to replay"
            )
        return self.dead_letters.pop(index)

    def report(self) -> str:
        if not self.dead_letters:
            return "no dead letters; every record found a home"
        by_reason: dict[str, int] = {}
        for letter in self.dead_letters:
            by_reason[letter.reason] = (
                by_reason.get(letter.reason, 0) + 1
            )
        lines = [
            f"{len(self.dead_letters)} dead letter(s), a work "
            "queue because each carries its provenance:"
        ]
        for reason in sorted(
            by_reason, key=lambda r: -by_reason[r]
        ):
            lines.append(f"  {by_reason[reason]}x {reason}")
        return "\n".join(lines)
