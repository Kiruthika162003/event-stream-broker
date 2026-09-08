"""Sasl reauth: a connection authenticated once must prove itself again in time.

Authenticating once when a connection opens is not enough for a
long-lived connection, because the credential that authenticated it
has a lifetime and a connection that stays open for days would keep
using a credential that expired long ago, defeating the point of
expiring credentials at all. Re-authentication closes that: the
broker tells the connection when its current authentication expires,
and the connection must re-authenticate over the same socket before
then, refreshing the session, or the broker treats it as
unauthenticated and stops serving it. This keeps a credential's
lifetime meaningful even for a connection that never closes, so
revoking or expiring a credential actually takes effect on live
connections rather than only on new ones. The enforcement is
strict on timing: a request arriving after the session expired with
no re-authentication is dropped, because serving it would honor an
expired credential, and the connection is closed so the client
reconnects and authenticates fresh. Re-authentication does not
reset the connection's identity, it refreshes the same principal's
session, so a connection cannot use re-auth to quietly become a
different principal mid-stream, which the manager enforces by
refusing a re-auth that presents a different principal than the one
the connection holds. The manager tracks the session expiry,
accepts a re-auth that extends it, refuses to serve past expiry
without one, and refuses a re-auth to a different principal. It
reports the time left before re-auth is required, because a client
that re-authenticates only after being cut off is one not tracking
its session expiry, reconnecting under load instead of refreshing
ahead of it.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Fenced, Invalid


@dataclass
class ReauthSession:
    principal: str
    session_expiry: int

    def reauthenticate(self, now: int, principal: str, new_expiry: int) -> str:
        if principal != self.principal:
            raise Fenced(
                f"re-auth presents '{principal}' but the connection holds "
                f"'{self.principal}'; a connection cannot become a different "
                "principal mid-stream"
            )
        if new_expiry <= now:
            raise Invalid("re-authentication must extend the session, not expire it")
        self.session_expiry = new_expiry
        return f"re-authenticated '{principal}'; session now to {new_expiry}"

    def serve(self, now: int, request: str) -> str:
        if now >= self.session_expiry:
            raise Invalid(
                f"'{request}' dropped: the session expired at "
                f"{self.session_expiry} with no re-auth; serving it would "
                "honor an expired credential, the connection is closed"
            )
        return f"served '{request}'"

    def time_left(self, now: int) -> str:
        left = self.session_expiry - now
        if left <= 0:
            return "session expired; re-auth required before any more requests"
        return (
            f"{left} until re-auth required; a client re-authenticating only "
            "after being cut off is not tracking its session expiry"
        )
