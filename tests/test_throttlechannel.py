from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.throttlechannel import ThrottleChannel


def channel() -> ThrottleChannel:
    return ThrottleChannel(client_id="ingest")


class TestResponding:
    def test_the_response_carries_the_throttle_time(self):
        c = channel()
        verdict = c.respond(now=0, throttle_ticks=40)
        assert "throttle-time 40" in verdict
        assert "not broker slowness" in verdict
        assert c.next_allowed_tick == 40

    def test_a_negative_throttle_is_refused(self):
        with pytest.raises(Invalid):
            channel().respond(now=0, throttle_ticks=-1)


class TestReceiving:
    def test_a_client_that_waits_is_accepted(self):
        c = channel()
        c.respond(now=0, throttle_ticks=40)
        verdict = c.receive(now=40)
        assert "accepted at the throttle boundary" in verdict
        assert c.honored == 1

    def test_a_client_that_sends_early_is_muted(self):
        c = channel()
        c.respond(now=0, throttle_ticks=40)
        verdict = c.receive(now=10)
        assert "held 30 tick(s)" in verdict
        assert "converge on the same rate" in verdict
        assert c.muted == 1


class TestBehavior:
    def test_a_well_behaved_client_reads_calm(self):
        c = channel()
        c.respond(0, 40)
        c.receive(40)
        assert "well-behaved, self-pacing" in c.behavior()

    def test_a_broken_backoff_is_flagged(self):
        c = channel()
        for _ in range(3):
            c.respond(0, 40)
            c.receive(10)
        behavior = c.behavior()
        assert "sent early 3 time(s)" in behavior
        assert "a broken backoff" in behavior

    def test_no_requests_yet(self):
        assert channel().behavior() == "no requests yet"
