"""Priority queue: always pop the smallest, in log time, with a binary heap.

Scheduling work by priority, the next delayed operation to fire by
its deadline, the most urgent request to serve, needs a structure
that returns the smallest element fast and stays cheap as elements
come and go. A sorted list gives an instant minimum but a linear
insert; a binary heap gives both a logarithmic insert and a
logarithmic pop of the minimum, which is the right balance when
both operations happen constantly. The heap is an array viewed as a
tree where each node is smaller than its children, so the minimum
is always at the root, index zero. A push appends at the end and
sifts up, swapping with its parent while it is smaller, restoring
the order in a logarithmic number of swaps. A pop takes the root as
the answer, moves the last element to the root, and sifts down,
swapping with its smaller child while it is larger, again
logarithmic. The heap property is local, each node versus its
children, which is what keeps the operations cheap: neither push
nor pop touches more than one root-to-leaf path. This is the
structure behind a timer that fires the earliest deadline and a
scheduler that runs the highest priority, where a full sort would
be wasted because only the minimum is ever needed next. The queue
pushes with a priority, pops the minimum, and peeks it without
removing, and it refuses a pop or peek of an empty queue, a normal
state the caller handles rather than reading a stale minimum. It
reports the size, because a queue that only grows is one where work
arrives faster than it is popped, the backlog a scheduler falling
behind accumulates."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class PriorityQueue:
    _heap: list[tuple[int, str]] = field(default_factory=list)

    def push(self, priority: int, item: str) -> None:
        self._heap.append((priority, item))
        i = len(self._heap) - 1
        while i > 0:
            parent = (i - 1) // 2
            if self._heap[i] < self._heap[parent]:
                self._heap[i], self._heap[parent] = self._heap[parent], self._heap[i]
                i = parent
            else:
                break

    def peek(self) -> tuple[int, str]:
        if not self._heap:
            raise Invalid("the queue is empty; no minimum to peek")
        return self._heap[0]

    def pop(self) -> tuple[int, str]:
        if not self._heap:
            raise Invalid("the queue is empty; nothing to pop")
        top = self._heap[0]
        last = self._heap.pop()
        if self._heap:
            self._heap[0] = last
            self._sift_down(0)
        return top

    def _sift_down(self, i: int) -> None:
        n = len(self._heap)
        while True:
            smallest = i
            left, right = 2 * i + 1, 2 * i + 2
            if left < n and self._heap[left] < self._heap[smallest]:
                smallest = left
            if right < n and self._heap[right] < self._heap[smallest]:
                smallest = right
            if smallest == i:
                break
            self._heap[i], self._heap[smallest] = self._heap[smallest], self._heap[i]
            i = smallest

    def size(self) -> str:
        return (
            f"{len(self._heap)} item(s) queued; a queue that only grows is work "
            "arriving faster than it is popped, a scheduler's backlog"
        )
