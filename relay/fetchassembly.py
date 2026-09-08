"""Fetch assembly: pack many partitions into one bounded response, fairly.

A fetch request names many partitions, and the response has a
size ceiling, so the broker must decide which partitions' data to
include when they do not all fit. The naive approach fills
partitions in request order until the response is full, and it
starves: the partitions late in the request never get their data
while the early ones are served every round, so a consumer sees
some partitions advance and others stall for no reason it can
see. Fair assembly rotates the starting partition each round, so
over successive fetches every partition gets its turn at the
front and none is permanently starved, the same round-robin
fairness a scheduler uses, applied to bytes in a response. The
one exception the assembler must honor is the oversized record:
a single record larger than the whole response budget is
returned alone in a response of its own, because a partition
whose next record cannot fit any response would otherwise stall
forever, served zero bytes every round while the fair rotation
politely skips it. So fairness has a floor: every partition
either makes progress or is explicitly the oversized-record case,
and a partition making zero progress for any other reason is a
bug the assembler is built to prevent. The report states which
partitions were served and which deferred, because a consumer
told its partition was deferred this round can wait calmly, while
one seeing an inexplicable stall starts filing tickets.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class FetchAssembler:
    response_budget: int
    rotation: int = 0

    def __post_init__(self) -> None:
        if self.response_budget < 1:
            raise Invalid("the response budget must be positive")

    def assemble(
        self, available: list[tuple[int, int]]
    ) -> tuple[list[int], list[int]]:
        if not available:
            raise Invalid("no partitions to assemble")
        n = len(available)
        order = [
            available[(self.rotation + i) % n] for i in range(n)
        ]
        served = []
        deferred = []
        used = 0
        for partition, size in order:
            if size > self.response_budget and not served:
                served.append(partition)
                used = size
                continue
            if used + size <= self.response_budget:
                served.append(partition)
                used += size
            else:
                deferred.append(partition)
        self.rotation = (self.rotation + 1) % n
        return sorted(served), sorted(deferred)

    def report(
        self, served: list[int], deferred: list[int]
    ) -> str:
        note = ""
        if deferred:
            note = (
                f"; {len(deferred)} deferred to a later round, "
                "which a consumer can wait on calmly"
            )
        return (
            f"{len(served)} partition(s) served this round{note}; "
            "fairness rotates so none starves"
        )
