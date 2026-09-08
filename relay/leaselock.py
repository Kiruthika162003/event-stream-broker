"""Lease lock: a lock that expires, so a crashed holder does not keep it forever.

A plain lock has a fatal flaw in a distributed system: if the
holder crashes while holding it, the lock is held forever and no
one else can proceed, because there is no one to release it. A
lease fixes that by making the lock time-bounded: it is held only
for a lease duration, and if the holder does not renew it before it
expires, it is automatically freed for someone else to acquire, so
a crashed holder's lock is released by the clock rather than by the
holder that can no longer act. The holder keeps the lock by renewing
before expiry, a heartbeat on the lock, and a holder that stops
renewing, because it crashed or paused, loses the lock at the next
expiry. This introduces the hazard that fencing tokens address: a
holder that paused, for a long garbage collection, past its lease
and then resumed still believes it holds the lock, while another has
acquired it, so both think they hold it, and the paused one acting
on that stale belief is a split brain. The lease alone cannot stop
that, which is why a resource guarded by a lease also checks a
fencing token, a number that increases each acquisition, and
rejects an operation carrying a token older than the highest it has
seen, so the resumed old holder is fenced. The lock grants to a
free or expired lease, refuses to grant one still held and unexpired
to another holder, lets the holder renew while it still holds, and
issues an increasing fencing token on each grant. It reports the
holder and time to expiry, and names that the token, not the lease,
is what actually prevents a paused holder from acting, because the
lease bounds the wait while the token bounds the damage."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class LeaseLock:
    lease_duration: int
    holder: str = ""
    expires_at: int = -1
    fencing_token: int = 0

    def __post_init__(self) -> None:
        if self.lease_duration < 1:
            raise Invalid("the lease duration must be positive")

    def _held(self, now: int) -> bool:
        return bool(self.holder) and now < self.expires_at

    def acquire(self, who: str, now: int) -> int:
        if self._held(now) and self.holder != who:
            raise Invalid(
                f"lock held by '{self.holder}' until {self.expires_at}; not "
                "granting to another until it expires or is released"
            )
        self.holder = who
        self.expires_at = now + self.lease_duration
        self.fencing_token += 1
        return self.fencing_token

    def renew(self, who: str, now: int) -> str:
        if not self._held(now) or self.holder != who:
            raise Invalid(
                f"'{who}' does not hold the lock (holder '{self.holder}'); a "
                "holder that stopped renewing loses it at expiry"
            )
        self.expires_at = now + self.lease_duration
        return f"renewed by '{who}' until {self.expires_at}"

    def guard(self, token: int) -> str:
        if token < self.fencing_token:
            raise Invalid(
                f"fencing token {token} is older than {self.fencing_token}; a "
                "paused holder resumed after its lease, fenced from acting"
            )
        return f"operation with token {token} allowed"

    def status(self, now: int) -> str:
        if not self._held(now):
            return "lock free or lease expired; acquirable"
        return (
            f"held by '{self.holder}', expires in {self.expires_at - now}; the "
            "fencing token, not the lease, prevents a paused holder from acting"
        )
