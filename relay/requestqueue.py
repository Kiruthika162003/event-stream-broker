"""Request queue: an overloaded broker sheds load instead of melting.

A broker under more load than it can handle has two behaviors,
and only one is survivable. It can queue every request that
arrives, growing an unbounded backlog, so latency climbs until
the requests at the back time out anyway, having consumed memory
and made the broker slower for nothing, the death spiral where a
temporarily overloaded broker becomes a permanently useless one.
Or it can bound the queue and reject requests that arrive when it
is full, immediately, so the client learns at once that the
broker is saturated and can back off or try another broker, and
the requests the broker does accept it can actually serve within
their deadline. Bounded rejection is strictly better under
overload because a request rejected in one millisecond is a
better answer than the same request served in thirty seconds
after its caller gave up, and a broker that sheds the excess
keeps serving the load it accepted at full speed. The queue also
prioritizes: a controller request that moves leadership must not
wait behind a thousand ordinary produces, because the control
plane recovering is what ends the overload, so control requests
jump the queue while data requests take their bounded turn, and
the report separates rejections into shed-under-load from
control-preserved, since a queue that rejected a leadership
change to serve a produce optimized exactly the wrong thing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class RequestQueue:
    capacity: int
    control: list[str] = field(default_factory=list)
    data: list[str] = field(default_factory=list)
    shed: int = 0

    def __post_init__(self) -> None:
        if self.capacity < 1:
            raise Invalid("the queue needs capacity")

    def _depth(self) -> int:
        return len(self.control) + len(self.data)

    def offer(self, request: str, is_control: bool) -> str:
        if is_control:
            self.control.append(request)
            return f"{request} enqueued ahead of data (control)"
        if self._depth() >= self.capacity:
            self.shed += 1
            return (
                f"{request} shed: queue full at {self.capacity}, "
                "rejected in a moment because that beats serving "
                "it after its caller gave up"
            )
        self.data.append(request)
        return f"{request} enqueued"

    def next_request(self) -> str:
        if self.control:
            return self.control.pop(0)
        if self.data:
            return self.data.pop(0)
        raise Invalid("the queue is empty")

    def report(self) -> str:
        return (
            f"{self._depth()} queued ({len(self.control)} "
            f"control ahead), {self.shed} shed under load; "
            "control preserved, because a queue that rejected a "
            "leadership change to serve a produce optimized the "
            "wrong thing"
        )
