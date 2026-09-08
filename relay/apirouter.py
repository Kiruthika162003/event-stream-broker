"""Api router: dispatch by key and version, and reject what cannot be served.

Every request names an api key, which request it is, produce or
fetch or metadata, and a version, which revision of that request's
format it speaks, and the broker routes it to the handler for that
key at that version. The router is where two mismatches are caught
before a handler ever sees a request it cannot parse. An unknown
api key is a request the broker has no handler for at all, either a
client speaking a protocol this broker does not implement or a
corrupt key, and it is rejected outright rather than dispatched to
a default that would misread it. An unsupported version is subtler:
the key is known but the client asked for a version outside the
range the handler supports, either older than the broker still
accepts or newer than it understands, and the fix differs by
direction, an old client should be told the minimum the broker
supports and a client from the future told the maximum, so the
rejection names the supported range rather than a bare refusal. The
router refuses a version below the handler's minimum and above its
maximum with that range in the error, and it refuses an unknown key
distinctly from an unsupported version, because the two send the
client to different remedies, upgrade the client versus route to a
broker that implements the key. It reports the api keys it serves
and their version ranges, which is exactly what an api-versions
request returns to a client so the client can negotiate down to a
version both sides speak before sending the real request, turning a
would-be rejection into a negotiation that succeeds.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid, Missing


@dataclass
class ApiRouter:
    handlers: dict[str, tuple[int, int]] = field(default_factory=dict)

    def register(self, key: str, min_version: int, max_version: int) -> None:
        if min_version > max_version:
            raise Invalid(
                f"handler '{key}' min version {min_version} exceeds max "
                f"{max_version}"
            )
        self.handlers[key] = (min_version, max_version)

    def route(self, key: str, version: int) -> str:
        if key not in self.handlers:
            raise Missing(
                f"no handler for api key '{key}'; the broker does not "
                "implement it, upgrade the client or route to a broker "
                "that does, distinct from an unsupported version"
            )
        low, high = self.handlers[key]
        if version < low:
            raise Invalid(
                f"'{key}' version {version} is below the broker's "
                f"minimum {low}; an old client should negotiate up to "
                f"the supported range {low}..{high}"
            )
        if version > high:
            raise Invalid(
                f"'{key}' version {version} is above the broker's "
                f"maximum {high}; a client from the future should "
                f"negotiate down to the supported range {low}..{high}"
            )
        return f"routed '{key}' v{version} to its handler"

    def advertised_versions(self) -> dict[str, tuple[int, int]]:
        return dict(self.handlers)
