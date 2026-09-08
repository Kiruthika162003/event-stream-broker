"""Max block: send waits this long for room to send, then it fails, not hangs.

A producer's send call is not always instant: it may have to wait,
for metadata the first time it sends to a topic it does not know
yet, and for buffer space when the accumulator is full because the
broker is not draining as fast as the application is producing. The
max-block budget bounds that total wait: send blocks up to the
budget across both waits, and if the budget elapses before it can
proceed, it fails the send rather than blocking forever, so a slow
or unreachable broker turns into an error the application handles
rather than a hang that stalls the whole producer thread. The
budget is shared, not per-wait, so a send that spends most of the
budget waiting for metadata has little left for buffer space, which
is why the first send to a new topic against a slow cluster is the
one most likely to time out. The calculator tracks how much budget
a send has consumed across its waits and decides whether it can
still proceed or must fail, and it names which wait exhausted the
budget, metadata or buffer, because the two point at different
problems, a metadata timeout is a cluster the client cannot reach
while a buffer timeout is a broker too slow to drain what the
application produces. It refuses a zero or negative budget, which
would make send fail instantly under any back-pressure rather than
absorbing a brief pause, defeating the buffering that smooths a
bursty producer. It reports the budget remaining after the waits so
far, because a send routinely consuming most of its budget is a
producer near the edge of timing out, the warning before sends
start failing under a load that grew past the broker's drain rate.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class BlockBudget:
    budget: int
    spent_on_metadata: int = 0
    spent_on_buffer: int = 0

    def __post_init__(self) -> None:
        if self.budget <= 0:
            raise Invalid(
                "a zero max-block makes send fail instantly under any "
                "back-pressure, defeating the buffering that smooths bursts"
            )

    def wait_metadata(self, ticks: int) -> None:
        self.spent_on_metadata += ticks

    def wait_buffer(self, ticks: int) -> None:
        self.spent_on_buffer += ticks

    def spent(self) -> int:
        return self.spent_on_metadata + self.spent_on_buffer

    def remaining(self) -> int:
        return max(0, self.budget - self.spent())

    def can_proceed(self) -> bool:
        return self.spent() <= self.budget

    def resolve(self) -> str:
        if self.can_proceed():
            return (
                f"send proceeds; {self.remaining()} of {self.budget} budget "
                "left, a send routinely near zero is near timing out"
            )
        culprit = (
            "metadata (a cluster the client cannot reach)"
            if self.spent_on_metadata >= self.spent_on_buffer
            else "buffer (a broker too slow to drain)"
        )
        return (
            f"send fails: {self.spent()} spent over the {self.budget} "
            f"budget, mostly on {culprit}, an error not a hang"
        )
