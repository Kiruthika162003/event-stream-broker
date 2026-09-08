"""A security day: authenticate, map, tokenize, re-auth, all under a quota.

Run with: python -m examples.securityday
"""

from __future__ import annotations

from relay.connectionquota import ConnectionQuota
from relay.delegationtoken import DelegationToken
from relay.principalmapping import MappingRule, PrincipalMapper
from relay.sasl import SaslHandshake
from relay.saslreauth import ReauthSession


def morning_the_handshake():
    hs = SaslHandshake(enabled_mechanisms=("SCRAM-SHA-256", "PLAIN"))
    hs.choose("SCRAM-SHA-256")
    hs.exchange(done=False)
    print(f"morning: {hs.exchange(done=True)}")


def midmorning_map_to_a_principal():
    mapper = PrincipalMapper(
        rules=[
            MappingRule(prefix="CN=alice,", principal="alice"),
            MappingRule(prefix="CN=", principal="generic-cert-user"),
        ]
    )
    print(f"         {mapper.explain('CN=alice,OU=eng')}")


def noon_a_delegation_token():
    token = DelegationToken(issued_at=0, expiry=100, max_lifetime_at=1000)
    print(f"noon:    {token.authenticate(now=50)}")
    print(f"         {token.renew(now=90, extend_to=200)}")


def afternoon_reauth_before_expiry():
    session = ReauthSession(principal="alice", session_expiry=100)
    print(f"afternoon: {session.reauthenticate(now=90, principal='alice', new_expiry=300)}")
    print(f"           {session.serve(now=250, request='fetch')}")


def evening_under_a_connection_quota():
    quota = ConnectionQuota(per_ip_cap=2, broker_cap=100)
    quota.open("10.0.0.5")
    quota.open("10.0.0.5")
    try:
        quota.open("10.0.0.5")
    except Exception as caught:
        print(f"evening: {caught}")


def main() -> int:
    morning_the_handshake()
    midmorning_map_to_a_principal()
    noon_a_delegation_token()
    afternoon_reauth_before_expiry()
    evening_under_a_connection_quota()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
