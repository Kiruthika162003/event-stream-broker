"""Stream join: two streams meet only within a window, and only if co-located.

Joining two streams pairs a record from one with records from the
other that share a key and fall close in time, close meaning within
a join window, because two unbounded streams cannot be joined
without a time bound: every record would have to be kept forever
waiting for a match that might arrive at any future moment. The
window makes the join finite: a record from the left stream joins
records from the right whose timestamps are within the window
before or after it, so the state each side must keep is only a
window's worth of recent records, not the whole history. The join
has a precondition that is easy to forget and expensive to violate:
the two streams must be co-partitioned, meaning the same number of
partitions and the same keying, so that records with the same key
land on the same task where they can meet. If the streams have
different partition counts, a key on the left and the same key on
the right are on different tasks and can never be compared, so the
join silently produces nothing, which is why the joiner refuses
streams whose partition counts differ rather than running and
emitting an empty result that looks like no matches. The joiner
keeps each side's records within the window and, for an arriving
record, emits a joined pair for every opposite-side record with the
same key inside the window, dropping from state the records that
have aged past the window because they can no longer match anything
arriving. The report states the window's span and the state size it
implies, because a window widened for more matches is also a window
that holds more records in memory, and the two move together.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class StreamJoin:
    window: int
    left_partitions: int
    right_partitions: int
    left_state: list[tuple[str, int]] = field(default_factory=list)
    right_state: list[tuple[str, int]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.left_partitions != self.right_partitions:
            raise Invalid(
                f"streams are not co-partitioned ({self.left_partitions} "
                f"vs {self.right_partitions}); same-key records land on "
                "different tasks and can never meet, so the join would "
                "silently emit nothing"
            )
        if self.window < 0:
            raise Invalid("the join window cannot be negative")

    def _expire(self, state: list[tuple[str, int]], now: int) -> None:
        state[:] = [(k, t) for k, t in state if now - t <= self.window]

    def arrive_left(self, key: str, time: int) -> list[tuple[str, int, int]]:
        self._expire(self.right_state, time)
        matches = [
            (key, time, t)
            for k, t in self.right_state
            if k == key and abs(time - t) <= self.window
        ]
        self.left_state.append((key, time))
        return matches

    def arrive_right(self, key: str, time: int) -> list[tuple[str, int, int]]:
        self._expire(self.left_state, time)
        matches = [
            (key, t, time)
            for k, t in self.left_state
            if k == key and abs(time - t) <= self.window
        ]
        self.right_state.append((key, time))
        return matches

    def state_note(self) -> str:
        held = len(self.left_state) + len(self.right_state)
        return (
            f"window {self.window} holds {held} record(s) in join "
            "state; a wider window matches more and holds more, the "
            "two moving together"
        )
