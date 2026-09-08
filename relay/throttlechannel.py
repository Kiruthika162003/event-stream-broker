"""Throttle channel: tell the client how long to wait, and mute it meanwhile.

When a quota throttles a client, the broker has to communicate the
throttle without making the throttling worse, and the naive way
makes it worse. If the broker simply delays the response, the
client sees latency, assumes the broker is slow, and often retries
or opens more connections, adding load at the exact moment the
broker was trying to shed it. The throttle channel instead returns
the throttle-time explicitly in the response: the broker answers
immediately with the data and a field saying wait this long before
your next request, so the client learns the delay is deliberate
and self-paces rather than retrying. The subtlety is enforcement:
a well-behaved client honors the returned throttle-time, but a
broker cannot trust every client to, so it also mutes the channel
on its side, refusing to process the client's next request until
the throttle-time has elapsed, and a client that ignores the field
and sends early gets its request held, not rejected, so honoring
or ignoring the field converge on the same rate. The two
mechanisms together, the advisory field and the enforced mute, are
belt and suspenders on purpose: the field lets good clients
self-pace efficiently without holding a connection, and the mute
makes the rate hold even for clients that ignore the field. The
channel reports whether a client is honoring its throttle-times,
because a client that always sends exactly at the throttle
boundary is well-behaved while one that sends early every time and
gets muted is a client with a broken backoff, worth flagging to
its owner before it is throttled harder for load it need not
generate.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class ThrottleChannel:
    client_id: str
    next_allowed_tick: int = 0
    honored: int = 0
    muted: int = 0

    def respond(self, now: int, throttle_ticks: int) -> str:
        if throttle_ticks < 0:
            raise Invalid("throttle time cannot be negative")
        self.next_allowed_tick = now + throttle_ticks
        return (
            f"data returned now with throttle-time "
            f"{throttle_ticks}; wait before the next request, a "
            "deliberate delay not broker slowness"
        )

    def receive(self, now: int) -> str:
        if now < self.next_allowed_tick:
            self.muted += 1
            wait = self.next_allowed_tick - now
            return (
                f"held {wait} tick(s): the client ignored its "
                "throttle-time and sent early, so honoring and "
                "ignoring the field converge on the same rate"
            )
        self.honored += 1
        return "request accepted at the throttle boundary"

    def behavior(self) -> str:
        total = self.honored + self.muted
        if total == 0:
            return "no requests yet"
        if self.muted > self.honored:
            return (
                f"{self.client_id} sent early {self.muted} time(s) "
                f"vs honored {self.honored}: a broken backoff "
                "worth flagging before it is throttled harder for "
                "load it need not generate"
            )
        return (
            f"{self.client_id} honored {self.honored}, muted "
            f"{self.muted}: well-behaved, self-pacing on the field"
        )
