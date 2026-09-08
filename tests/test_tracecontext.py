from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.tracecontext import TracePropagator


def propagator() -> TracePropagator:
    p = TracePropagator()
    p.set_client("traceparent", "00-abc-def-01")
    p.set_client("tracestate", "vendor=1")
    return p


class TestPropagation:
    def test_client_headers_reach_the_consumer_unchanged(self):
        p = propagator()
        delivered = p.delivered_to_consumer()
        assert delivered["traceparent"] == "00-abc-def-01"
        assert delivered["tracestate"] == "vendor=1"

    def test_the_broker_adds_its_own_span_alongside(self):
        p = propagator()
        p.add_broker_span("ingest", "t=105")
        delivered = p.delivered_to_consumer()
        assert delivered["__relay.span.ingest"] == "t=105"
        assert delivered["traceparent"] == "00-abc-def-01"

    def test_a_client_cannot_forge_a_broker_span(self):
        p = TracePropagator()
        with pytest.raises(Invalid) as caught:
            p.set_client("__relay.span.x", "fake")
        assert "cannot forge the broker's trace span" in str(
            caught.value
        )

    def test_a_broker_span_cannot_collide_with_a_client_header(self):
        p = TracePropagator()
        p.client_headers["__relay.span.ingest"] = "sneaked"
        with pytest.raises(Invalid) as caught:
            p.add_broker_span("ingest", "t=1")
        assert "break the trace the broker is enriching" in str(
            caught.value
        )


class TestSurvival:
    def test_an_intact_trace_is_confirmed(self):
        p = propagator()
        received = p.delivered_to_consumer()
        assert "trace intact" in p.trace_survived(received)

    def test_a_changed_header_is_a_propagation_bug(self):
        p = propagator()
        received = dict(p.delivered_to_consumer())
        received["traceparent"] = "00-tampered-01"
        verdict = p.trace_survived(received)
        assert "BROKEN" in verdict
        assert "a propagation bug" in verdict
