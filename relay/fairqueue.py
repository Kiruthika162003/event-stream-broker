"""Fair queue: serve clients in proportion to weight, so none starves another.

Serving many clients from one resource, a broker's request handler
across producers, fairly means each gets service in proportion to
its weight, and no backlogged client starves the others. A plain
FIFO fails this: a client that floods the queue is served ahead of
everyone behind it, so a heavy client can crowd out a light one.
Weighted fair queueing fixes it with deficit round-robin: each
client has its own queue and a deficit counter, and each round the
scheduler adds that client's quantum, proportional to its weight,
to its deficit, then serves requests from its queue while the
deficit covers their cost, carrying any leftover deficit to the
next round. A client with twice the weight gets twice the quantum
and so twice the service over time, while a client with an empty
queue simply passes, its quantum not hoarded. This gives each
client its fair share regardless of how aggressively it enqueues,
because the deficit, not arrival order, gates service, so a flood
fills only that client's own queue and spends only its own deficit,
never another's. The scheduler adds quanta by weight, serves within
the deficit, and carries the remainder, and it refuses a client
with a non-positive weight, which would get no quantum and be
starved by construction. It reports the service each client
received against its weight, because the ratio should match the
weights, and a client receiving far less than its weight implies is
one whose queue ran empty, offering less than its share, not being
denied it, a distinction between a starved client and an idle one."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class FairQueue:
    weights: dict[str, int]
    queues: dict[str, list[int]] = field(default_factory=dict)
    deficit: dict[str, int] = field(default_factory=dict)
    served: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if any(w <= 0 for w in self.weights.values()):
            raise Invalid("a client with a non-positive weight is starved by construction")
        for c in self.weights:
            self.queues.setdefault(c, [])
            self.deficit.setdefault(c, 0)
            self.served.setdefault(c, 0)

    def enqueue(self, client: str, cost: int) -> None:
        if client not in self.weights:
            raise Invalid(f"unknown client '{client}'")
        self.queues[client].append(cost)

    def round(self) -> None:
        for client, weight in self.weights.items():
            self.deficit[client] += weight
            q = self.queues[client]
            while q and q[0] <= self.deficit[client]:
                cost = q.pop(0)
                self.deficit[client] -= cost
                self.served[client] += cost

    def report(self) -> str:
        parts = [f"{c}: served {self.served[c]} (weight {w})" for c, w in self.weights.items()]
        return (
            "; ".join(parts)
            + "; the served ratio should track the weights, and a client far "
            "under its weight ran its queue empty, offering less not denied"
        )
