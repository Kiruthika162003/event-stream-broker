from __future__ import annotations

import pytest

from relay.errors import Fenced, Invalid
from relay.saslreauth import ReauthSession


class TestServe:
    def test_serving_before_expiry_works(self):
        s = ReauthSession(principal="alice", session_expiry=100)
        assert s.serve(now=50, request="fetch") == "served 'fetch'"

    def test_serving_after_expiry_is_dropped(self):
        s = ReauthSession(principal="alice", session_expiry=100)
        with pytest.raises(Invalid) as caught:
            s.serve(now=150, request="fetch")
        assert "connection is closed" in str(caught.value)


class TestReauth:
    def test_reauth_extends_the_session(self):
        s = ReauthSession(principal="alice", session_expiry=100)
        s.reauthenticate(now=90, principal="alice", new_expiry=200)
        assert s.serve(now=150, request="produce") == "served 'produce'"

    def test_reauth_to_a_different_principal_is_fenced(self):
        s = ReauthSession(principal="alice", session_expiry=100)
        with pytest.raises(Fenced) as caught:
            s.reauthenticate(now=90, principal="mallory", new_expiry=200)
        assert "different principal mid-stream" in str(caught.value)

    def test_a_reauth_that_does_not_extend_is_refused(self):
        s = ReauthSession(principal="alice", session_expiry=100)
        with pytest.raises(Invalid):
            s.reauthenticate(now=90, principal="alice", new_expiry=80)


class TestTimeLeft:
    def test_time_left_before_expiry(self):
        s = ReauthSession(principal="alice", session_expiry=100)
        assert "40 until re-auth required" in s.time_left(now=60)

    def test_expired_session_demands_reauth(self):
        s = ReauthSession(principal="alice", session_expiry=100)
        assert "re-auth required before any more" in s.time_left(now=150)
