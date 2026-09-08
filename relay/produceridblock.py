"""Producer id block: hand brokers ranges of ids so each id is not a round trip.

Every idempotent or transactional producer needs a unique producer
id, and if a broker asked the controller for one id at a time,
initializing producers would cost a controller round trip each,
making producer startup a bottleneck on one central service. So ids
are allocated in blocks: the controller hands a broker a contiguous
range at once, and the broker satisfies producer id requests from
its block locally until the block runs out, then asks for another.
The invariant that must never break is uniqueness across the whole
cluster: two producers with the same id would have their sequence
numbers confused, so a duplicate from one could be accepted as new
because the other advanced the sequence. Uniqueness holds because
the controller never hands the same range to two brokers and never
reuses a range, so ids are globally unique and monotonic across
blocks even though each broker allocates from its own block
independently. The allocator refuses to hand out an id past its
block's end, returning a signal to refill instead, because handing
out an id it does not own would collide with the broker that owns
the next block. It refuses a refill that overlaps the last block,
the controller bug that would break uniqueness, and it tracks how
much of the current block remains so a broker refills before it
runs dry rather than stalling producer initialization at the
moment the block empties. The report states the block's remaining
capacity, because a broker burning through blocks quickly is one
with a storm of short-lived producers each taking an id and never
returning, worth catching before id allocation itself becomes the
bottleneck the blocks were meant to remove.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class ProducerIdBlock:
    block_start: int
    block_size: int
    next_id: int = -1

    def __post_init__(self) -> None:
        if self.block_size < 1:
            raise Invalid("a block must have positive size")
        if self.next_id < 0:
            self.next_id = self.block_start

    def block_end(self) -> int:
        return self.block_start + self.block_size

    def allocate(self) -> int:
        if self.next_id >= self.block_end():
            raise Invalid(
                "the block is exhausted; refill before handing out an "
                "id it does not own, which would collide with the "
                "broker owning the next block"
            )
        allocated = self.next_id
        self.next_id += 1
        return allocated

    def remaining(self) -> int:
        return self.block_end() - self.next_id

    def refill(self, new_start: int, new_size: int) -> str:
        if new_start < self.block_end():
            raise Invalid(
                f"refill start {new_start} overlaps the last block "
                f"ending {self.block_end()}; overlapping ranges break "
                "cluster-wide uniqueness"
            )
        self.block_start = new_start
        self.block_size = new_size
        self.next_id = new_start
        return f"refilled block [{new_start}, {self.block_end()})"

    def health(self) -> str:
        return (
            f"{self.remaining()} id(s) left in the block; a broker "
            "burning blocks fast has a storm of short-lived producers, "
            "worth catching before id allocation becomes the bottleneck"
        )
