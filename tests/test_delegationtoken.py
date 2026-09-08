from __future__ import annotations

import pytest

from relay.delegationtoken import DelegationToken
from relay.errors import Invalid


def _token():
    return DelegationToken(issued_at=0, expiry=100, max_lifetime_at=1000)


class TestUsable:
    def test_a_fresh_token_authenticates(self):
        t = _token()
        assert "authenticated" in t.authenticate(now=50)

    def test_an_expired_token_is_refused(self):
        t = _token()
        with pytest.raises(Invalid) as caught:
            t.authenticate(now=150)
        assert "expired at 100" in str(caught.value)

    def test_an_initial_expiry_past_max_lifetime_is_refused(self):
        with pytest.raises(Invalid):
            DelegationToken(issued_at=0, expiry=2000, max_lifetime_at=1000)


class TestRenew:
    def test_renewal_extends_the_expiry(self):
        t = _token()
        t.renew(now=90, extend_to=200)
        assert t.is_usable(now=150)

    def test_renewal_past_max_lifetime_is_refused(self):
        t = _token()
        with pytest.raises(Invalid) as caught:
            t.renew(now=90, extend_to=1500)
        assert "must re-authenticate" in str(caught.value)


class TestRevoke:
    def test_a_revoked_token_is_dead_before_expiry(self):
        t = _token()
        t.revoke()
        assert not t.is_usable(now=50)
        with pytest.raises(Invalid):
            t.authenticate(now=50)

    def test_a_revoked_token_cannot_renew(self):
        t = _token()
        t.revoke()
        with pytest.raises(Invalid):
            t.renew(now=50, extend_to=200)


class TestStatus:
    def test_status_reports_both_horizons(self):
        note = _token().status(now=40)
        assert "60 until expiry" in note
        assert "960 until re-auth" in note
