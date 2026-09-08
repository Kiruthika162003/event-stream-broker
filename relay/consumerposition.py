"""Consumer position: three offsets people conflate, and the order between them.

A consumer has three offsets on a partition and confusing them is
behind a whole class of bugs. The position is the offset the
consumer will fetch next, advancing as it reads. The committed
offset is the position it last saved to the coordinator, where it
would resume after a restart. The high watermark is the end of the
readable log, one past the last committed record on the broker.
These have a fixed order that the model enforces as invariants. The
committed offset cannot exceed the position, because committing an
offset means promising everything before it was processed, and a
consumer cannot have processed records it has not yet fetched, so a
commit ahead of the position would skip records on restart. The
position cannot exceed the high watermark, because the consumer
cannot fetch records the broker has not made readable, so a
position past the watermark is reading the future. The gap between
the position and the committed offset is the replay window, the
records that would be reprocessed if the consumer crashed now, and
the gap between the high watermark and the position is the lag, the
records waiting to be read. The model refuses to advance the
position past the watermark and to commit past the position,
naming which invariant broke, because the two failures mean
different bugs: a position past the watermark is a fetch offset
computed wrong, while a commit past the position is a commit of
work not done. The report states all three offsets and the two
gaps, because an operator looking at lag alone cannot tell a
consumer that is behind but committing steadily from one that is
reading fast but not committing, a crash away from a large replay.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class ConsumerPosition:
    high_watermark: int
    position: int = 0
    committed: int = 0

    def __post_init__(self) -> None:
        if self.position > self.high_watermark:
            raise Invalid("position cannot start past the high watermark")
        if self.committed > self.position:
            raise Invalid("committed cannot start past the position")

    def advance_position(self, to: int) -> None:
        if to > self.high_watermark:
            raise Invalid(
                f"position {to} is past the high watermark "
                f"{self.high_watermark}; that is reading the future, a "
                "fetch offset computed wrong"
            )
        if to < self.position:
            raise Invalid("position only advances, use seek to move back")
        self.position = to

    def commit(self, to: int) -> None:
        if to > self.position:
            raise Invalid(
                f"commit {to} is past the position {self.position}; that "
                "promises work not done and would skip records on restart"
            )
        self.committed = to

    def replay_window(self) -> int:
        return self.position - self.committed

    def lag(self) -> int:
        return self.high_watermark - self.position

    def report(self) -> str:
        return (
            f"position {self.position}, committed {self.committed}, "
            f"watermark {self.high_watermark}; replay window "
            f"{self.replay_window()}, lag {self.lag()}; lag alone hides "
            "a fast reader not committing, a crash from a large replay"
        )
