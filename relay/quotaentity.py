"""Quota entity: the most specific match sets the limit, defaults fill the rest.

A quota is not attached to one thing but to an entity, and the
entity can be a specific user, a specific client id, the pair of
both, or a cluster-wide default, which lets an operator say this one
user is capped here, this misbehaving client id there, and everyone
else at the default. When a request arrives carrying a user and a
client id, the broker must decide which of the possibly several
matching quotas applies, and the rule is most-specific-wins in a
fixed precedence: a quota for the exact user-and-client-id pair
beats one for the user alone, which beats one for the client id
alone, which beats the cluster default. This precedence is what
lets a broad default coexist with targeted overrides without them
fighting, the same shape as config inheritance but over a two-
dimensional entity space rather than a linear one. The resolver
walks the precedence order and returns the first quota that exists
along with which entity level set it, because an operator debugging
why a client is throttled at a surprising rate needs to know
whether the limit came from a pair-specific override, a user
default, or the cluster default, since that decides where to change
it. The resolver refuses to resolve when not even a cluster default
exists, because a request with no applicable quota at any level
means quotas were never configured, an unlimited state the operator
should see rather than have the resolver invent a limit. It reports
the matched entity so a throttle is explained by its source, not
just its value, turning an opaque limit into one an operator can
trace to the entity that set it and adjust there.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Missing

PAIR = "user+client"
USER = "user"
CLIENT = "client"
DEFAULT = "default"


@dataclass
class QuotaResolver:
    pair: dict[tuple[str, str], int] = field(default_factory=dict)
    per_user: dict[str, int] = field(default_factory=dict)
    per_client: dict[str, int] = field(default_factory=dict)
    cluster_default: int | None = None

    def resolve(self, user: str, client: str) -> tuple[int, str]:
        if (user, client) in self.pair:
            return self.pair[(user, client)], PAIR
        if user in self.per_user:
            return self.per_user[user], USER
        if client in self.per_client:
            return self.per_client[client], CLIENT
        if self.cluster_default is not None:
            return self.cluster_default, DEFAULT
        raise Missing(
            f"no quota applies to user '{user}' client '{client}' at any "
            "level; quotas were never configured, an unlimited state to see"
        )

    def describe(self, user: str, client: str) -> str:
        limit, level = self.resolve(user, client)
        return (
            f"user '{user}' client '{client}' limited to {limit} by the "
            f"{level} entity; change it there"
        )
