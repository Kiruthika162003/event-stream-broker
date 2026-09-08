from __future__ import annotations

import pytest

from relay.errors import Fenced, Invalid
from relay.sasl import COMPLETE, FAILED, SaslHandshake


def _handshake():
    return SaslHandshake(enabled_mechanisms=("SCRAM-SHA-256", "PLAIN"))


class TestChoose:
    def test_an_enabled_mechanism_is_chosen(self):
        h = _handshake()
        assert "chose PLAIN" in h.choose("PLAIN")

    def test_a_disabled_mechanism_is_refused_not_downgraded(self):
        h = _handshake()
        with pytest.raises(Invalid) as caught:
            h.choose("GSSAPI")
        assert "not enabled" in str(caught.value)
        assert "strips authentication" in str(caught.value)


class TestExchange:
    def test_a_single_round_can_complete(self):
        h = _handshake()
        h.choose("PLAIN")
        assert "complete after 1 round(s)" in h.exchange(done=True)
        assert h.state == COMPLETE

    def test_a_multi_round_mechanism_stays_authenticating(self):
        h = _handshake()
        h.choose("SCRAM-SHA-256")
        assert "more to go" in h.exchange(done=False)
        assert "complete after 2 round(s)" in h.exchange(done=True)

    def test_a_failed_authentication_is_terminal(self):
        h = _handshake()
        h.choose("PLAIN")
        h.exchange(done=True, ok=False)
        assert h.state == FAILED
        with pytest.raises(Invalid):
            h.exchange(done=True)

    def test_exchanging_before_choosing_is_refused(self):
        h = _handshake()
        with pytest.raises(Invalid):
            h.exchange(done=True)


class TestMayServe:
    def test_traffic_before_complete_is_refused(self):
        h = _handshake()
        h.choose("PLAIN")
        with pytest.raises(Invalid) as caught:
            h.may_serve("produce")
        assert "unauthenticated peer" in str(caught.value)

    def test_traffic_after_complete_is_allowed(self):
        h = _handshake()
        h.choose("PLAIN")
        h.exchange(done=True)
        assert "authorized to proceed" in h.may_serve("produce")

    def test_a_second_handshake_after_complete_is_fenced(self):
        h = _handshake()
        h.choose("PLAIN")
        h.exchange(done=True)
        with pytest.raises(Fenced):
            h.choose("PLAIN")
