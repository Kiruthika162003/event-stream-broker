"""Protocol versioning: old clients and new brokers meet in the middle.

A broker and its clients upgrade on different schedules, so a
new broker must serve a client from three versions ago and an
old client must talk to a broker upgraded last night. The API
version negotiation makes this survivable: each request type
advertises a range of versions the broker supports, the client
advertises the range it supports, and they use the highest
version both understand. The negotiation refuses the two failure
modes explicitly. A client whose minimum exceeds the broker's
maximum is too new for this broker, and forcing it to downgrade
past its minimum would make it speak a dialect it has dropped, so
the connection is refused with the version gap named rather than
silently truncating fields. A client whose maximum is below the
broker's minimum is too old, its protocol retired, and it is told
to upgrade rather than served a best-effort translation that
loses the semantics the retirement removed. The negotiated
version is recorded per connection, because a broker that cannot
say which version it is speaking to a client cannot debug the
field that appeared in v5 and confused the v3 client that never
learned it.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class VersionRange:
    minimum: int
    maximum: int

    def __post_init__(self) -> None:
        if self.minimum > self.maximum:
            raise Invalid("a version range needs min <= max")

    def overlaps(self, other: VersionRange) -> bool:
        return (
            self.minimum <= other.maximum
            and other.minimum <= self.maximum
        )


def negotiate(
    request: str,
    broker: VersionRange,
    client: VersionRange,
) -> tuple[int, str]:
    if not broker.overlaps(client):
        if client.minimum > broker.maximum:
            raise Invalid(
                f"{request}: client min v{client.minimum} exceeds "
                f"broker max v{broker.maximum}; the client is too "
                "new, and downgrading past its minimum would make "
                "it speak a dialect it dropped"
            )
        raise Invalid(
            f"{request}: client max v{client.maximum} is below "
            f"broker min v{broker.minimum}; the client is too "
            "old, its protocol retired, and it must upgrade "
            "rather than get a lossy translation"
        )
    chosen = min(broker.maximum, client.maximum)
    return chosen, (
        f"{request} negotiated at v{chosen}; recorded so a field "
        "that appeared in a later version does not confuse a "
        "client that never learned it"
    )
