"""Delegation token: a short-lived credential that renews but not forever.

Handing a long-lived password to every worker that needs to talk to
the broker spreads a secret that is hard to rotate and dangerous if
leaked, so instead a client authenticates once and is issued a
delegation token: a short-lived credential it can use in place of
the password, easy to distribute to workers and cheap to revoke. A
token has two time bounds that serve different purposes. Its expiry
is soon, so a leaked token is useful only briefly, and the client
renews the token before it expires to keep working, each renewal
pushing the expiry out. But renewal is not unlimited: the token
also has a max lifetime from when it was issued, and once that is
reached the token cannot be renewed further and the client must
authenticate again to get a fresh one, so even a token that is
renewed diligently is retired on a schedule, bounding how long a
single issuance can live and how stale its original authentication
can get. The manager issues a token with an expiry and a max
lifetime, renews it by extending the expiry but never past the max
lifetime, and validates a token as usable only if it is unexpired
and not revoked. It refuses to renew a token past its max lifetime,
naming that the client must re-authenticate rather than renew, and
refuses to renew or use a revoked token, because revocation is
immediate and a revoked token is dead regardless of its expiry. It
reports how long a token has before expiry and before its max
lifetime, because the two answer different questions, when to renew
next and when re-authentication is coming, and a worker that
tracks only the expiry is surprised when a renewal is finally
refused at the max lifetime.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class DelegationToken:
    issued_at: int
    expiry: int
    max_lifetime_at: int
    revoked: bool = False

    def __post_init__(self) -> None:
        if self.expiry > self.max_lifetime_at:
            raise Invalid("initial expiry cannot exceed the max lifetime")

    def is_usable(self, now: int) -> bool:
        return not self.revoked and now < self.expiry

    def renew(self, now: int, extend_to: int) -> str:
        if self.revoked:
            raise Invalid("a revoked token is dead and cannot be renewed")
        if now >= self.expiry:
            raise Invalid(
                f"token already expired at {self.expiry}; an expired token "
                "is renewed by re-authenticating, not extending"
            )
        if extend_to > self.max_lifetime_at:
            raise Invalid(
                f"renewal to {extend_to} exceeds the max lifetime "
                f"{self.max_lifetime_at}; the client must re-authenticate "
                "for a fresh token, not renew this one"
            )
        self.expiry = extend_to
        return f"renewed; expiry now {self.expiry}, max lifetime {self.max_lifetime_at}"

    def revoke(self) -> None:
        self.revoked = True

    def authenticate(self, now: int) -> str:
        if self.revoked:
            raise Invalid("token revoked; authentication refused")
        if now >= self.expiry:
            raise Invalid(
                f"token expired at {self.expiry}; renew before expiry or "
                "re-authenticate"
            )
        return "authenticated by delegation token"

    def status(self, now: int) -> str:
        return (
            f"{max(0, self.expiry - now)} until expiry, "
            f"{max(0, self.max_lifetime_at - now)} until re-auth; a worker "
            "tracking only expiry is surprised when renewal is refused"
        )
