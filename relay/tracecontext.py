"""Trace context: the broker carries the trace without understanding it.

A record produced as part of a distributed trace carries a trace
context in its headers, and a consumer that processes it should
continue the same trace, so the span that produced the record and
the span that consumed it link into one story. The broker's job
here is precise and limited: it must carry the trace headers
through, from produce to the log to fetch, byte-for-byte
unchanged, without interpreting them, because the trace format is
the tracing system's concern and a broker that parsed it would
couple itself to a format it does not own and break when the
format evolves. The propagator enforces that the trace headers a
consumer receives are exactly the ones the producer set, so the
trace is not silently broken by a broker that dropped or
rewrote a header it did not recognize. The one thing the broker
does add is its own span, as a distinct header in the reserved
namespace, recording the record's time in the broker, so the
trace shows the broker hop as a span between produce and consume
rather than an unexplained gap, but it adds this alongside the
client's headers, never in place of them. The propagator refuses
to let a broker-added header collide with a client header,
because a broker overwriting a client's trace header would break
the very trace it is trying to enrich, and it reports whether a
record's trace survived the round trip intact, because a trace
that breaks at the broker sends the tracing team debugging the
broker when the break is a propagation bug the propagator exists
to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid

BROKER_SPAN_PREFIX = "__relay.span."


@dataclass
class TracePropagator:
    client_headers: dict[str, str] = field(default_factory=dict)
    broker_headers: dict[str, str] = field(default_factory=dict)

    def set_client(self, name: str, value: str) -> None:
        if name.startswith(BROKER_SPAN_PREFIX):
            raise Invalid(
                f"{name} is in the broker span namespace; a "
                "client cannot forge the broker's trace span"
            )
        self.client_headers[name] = value

    def add_broker_span(self, name: str, value: str) -> None:
        full = BROKER_SPAN_PREFIX + name
        if full in self.client_headers:
            raise Invalid(
                "a broker span cannot collide with a client "
                "header; overwriting it would break the trace the "
                "broker is enriching"
            )
        self.broker_headers[full] = value

    def delivered_to_consumer(self) -> dict[str, str]:
        return {**self.client_headers, **self.broker_headers}

    def trace_survived(
        self, received: dict[str, str]
    ) -> str:
        for name, value in self.client_headers.items():
            if received.get(name) != value:
                return (
                    f"BROKEN: client header {name} changed in "
                    "transit; a propagation bug, not a tracing-"
                    "team problem to debug in the broker"
                )
        return (
            "trace intact: every client header survived byte-for-"
            "byte, plus the broker's own span between produce and "
            "consume"
        )
