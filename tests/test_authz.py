from __future__ import annotations

import pytest

from relay.authz import Authorizer
from relay.errors import Invalid


def authorizer() -> Authorizer:
    built = Authorizer()
    built.grant("team-orders", "read", "orders-*")
    built.grant("team-orders", "write", "orders-events")
    return built


class TestDenyByDefault:
    def test_no_grant_means_denied(self):
        assert not authorizer().allowed(
            "intern", "read", "payroll"
        )

    def test_a_grant_allows(self):
        assert authorizer().allowed(
            "team-orders", "read", "orders-events"
        )

    def test_a_prefix_wildcard_covers_the_family(self):
        chosen = authorizer()
        assert chosen.allowed("team-orders", "read", "orders-dlq")

    def test_authorize_raises_on_denial(self):
        with pytest.raises(Invalid) as caught:
            authorizer().authorize("intern", "read", "payroll")
        assert "deny by default" in str(caught.value)


class TestExplicitDeny:
    def test_a_deny_outranks_a_grant(self):
        chosen = authorizer()
        chosen.deny("team-orders", "read", "orders-secret")
        assert not chosen.allowed(
            "team-orders", "read", "orders-secret"
        )
        assert chosen.allowed(
            "team-orders", "read", "orders-events"
        )

    def test_an_unknown_operation_is_refused(self):
        with pytest.raises(Invalid):
            authorizer().grant("p", "teleport", "t")


class TestAuditLog:
    def test_every_denial_is_logged(self):
        chosen = authorizer()
        chosen.allowed("intern", "read", "payroll")
        chosen.allowed("intern", "write", "orders-events")
        assert chosen.denials_logged == [
            "intern denied read on payroll",
            "intern denied write on orders-events",
        ]

    def test_wildcard_principal_grants_broadly(self):
        chosen = Authorizer()
        chosen.grant("*", "describe", "orders-events")
        assert chosen.allowed(
            "anyone", "describe", "orders-events"
        )
