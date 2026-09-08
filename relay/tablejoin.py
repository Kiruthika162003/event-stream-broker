"""Table join: two materialized tables, and an update on either re-emits.

A table-to-table join differs from a stream-to-stream join because
tables are not events that happen once, they are the current value
per key, so the join holds both sides materialized and the joined
result for a key is whatever the two sides currently say for it. An
update to either side re-emits the join for that key: if the left
side updates, the new left value is joined against the right side's
current value and the result changes, and the same for the right,
so the output is a table too, tracking the latest join of the
latest inputs. The case that catches people is the tombstone, a
null value that means a key was deleted. When one side sends a
tombstone for a key, the joined result for that key can no longer
hold, because one of its halves is gone, so the join emits a
tombstone downstream to withdraw the previously emitted result
rather than leaving a stale join that references a deleted row. The
join requires co-partitioning like the stream join, the same key on
both sides on the same task, so the joiner refuses mismatched
partition counts. An inner join emits a result only when both sides
have a value for the key, so a key present on one side and absent
on the other produces nothing, and the joiner distinguishes that
absence from a tombstone, because a key that never had a right-side
value was never joined and needs no withdrawal, while a key whose
right side was deleted had a result that must now be retracted. The
report states how many keys are currently joinable, both sides
present, against how many are half-present, because a table join
where most keys are half-present is two tables that do not share a
key space, a join that will mostly emit nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class TableJoin:
    left_partitions: int
    right_partitions: int
    left: dict[str, int] = field(default_factory=dict)
    right: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.left_partitions != self.right_partitions:
            raise Invalid(
                f"tables are not co-partitioned ({self.left_partitions} "
                f"vs {self.right_partitions}); same-key rows land on "
                "different tasks and cannot be joined"
            )

    def _joined(self, key: str) -> int | None:
        if key in self.left and key in self.right:
            return self.left[key] + self.right[key]
        return None

    def update_left(self, key: str, value: int | None) -> str:
        had = self._joined(key)
        if value is None:
            self.left.pop(key, None)
        else:
            self.left[key] = value
        now = self._joined(key)
        return self._emit(key, had, now)

    def update_right(self, key: str, value: int | None) -> str:
        had = self._joined(key)
        if value is None:
            self.right.pop(key, None)
        else:
            self.right[key] = value
        now = self._joined(key)
        return self._emit(key, had, now)

    def _emit(self, key: str, had: int | None, now: int | None) -> str:
        if now is not None:
            return f"{key}: joined = {now}"
        if had is not None:
            return f"{key}: tombstone, withdrawing the previous join"
        return f"{key}: no result, one side absent, nothing to withdraw"

    def joinable(self) -> str:
        both = len(set(self.left) & set(self.right))
        half = len(set(self.left) ^ set(self.right))
        return (
            f"{both} key(s) joinable, {half} half-present; mostly half-"
            "present is two tables that do not share a key space, a "
            "join that emits little"
        )
