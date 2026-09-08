"""Correlation id: many requests in flight, and each response finds its request.

A client does not wait for one response before sending the next; it
pipelines several requests on a connection at once to keep the link
busy, which means responses come back while other requests are
still outstanding, and the client must match each response to the
request that produced it. The match is a correlation id: the client
stamps each request with an id increasing per connection, the
broker echoes that id verbatim in the response, and the client
looks up the outstanding request by the id in the response. The
protocol guarantees one strong property that makes this reliable:
responses on a single connection come back in the order the
requests were sent, because the broker processes a connection's
requests in order and writes their responses in the same order, so
a client can also match by position, but the correlation id is the
explicit check that position did not drift. The tracker assigns
increasing ids, records each as outstanding when sent, and clears
it when its response arrives, and it catches two faults. A response
carrying an id that is not outstanding is a duplicate or a response
to a request the client already gave up on, and acting on it would
apply a stale answer. A response whose id is not the oldest
outstanding one violates the in-order guarantee, meaning the
connection's framing has desynchronized, and continuing to read it
would pair every later response with the wrong request. The tracker
refuses both rather than proceeding, because a mismatched
correlation id is not a recoverable hiccup on a stream protocol; it
means the byte stream is no longer aligned and the connection must
be torn down. The report states the outstanding count, because a
pipeline depth that keeps growing is a client sending faster than
the broker responds.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class CorrelationTracker:
    _next: int = 0
    outstanding: deque[int] = field(default_factory=deque)

    def send(self) -> int:
        correlation_id = self._next
        self._next += 1
        self.outstanding.append(correlation_id)
        return correlation_id

    def receive(self, correlation_id: int) -> str:
        if correlation_id not in self.outstanding:
            raise Invalid(
                f"correlation id {correlation_id} is not outstanding; "
                "a duplicate or a response to a request already given "
                "up on, and acting on it applies a stale answer"
            )
        oldest = self.outstanding[0]
        if correlation_id != oldest:
            raise Invalid(
                f"response {correlation_id} arrived before {oldest}; "
                "the in-order guarantee is broken, the byte stream has "
                "desynchronized and the connection must be torn down"
            )
        self.outstanding.popleft()
        return f"matched response {correlation_id}"

    def depth(self) -> str:
        return (
            f"{len(self.outstanding)} request(s) in flight; a depth "
            "that keeps growing is a client sending faster than the "
            "broker responds"
        )
