"""Headers: metadata about the delivery, kept out of the payload's meaning.

A record's value is what the application cares about; its headers
are what the infrastructure cares about, trace ids, source
service, content type, schema version, all the metadata that
routes and observes a record without being part of what it says.
Keeping them separate is the discipline: a system that stuffs
routing metadata into the value forces every consumer to parse
past infrastructure concerns to reach the data, and a schema
change to the metadata breaks the value's schema. The header
store enforces two rules that keep the separation clean. Headers
are ordered and may repeat, because some metadata is genuinely a
list, several trace spans, several forwarding hops, and a map
that silently kept only the last would lose the chain. But the
broker reserves a namespace prefix for its own headers, the ones
it sets for exactly-once sequence tracking and transaction
markers, and refuses a producer that tries to set a reserved
header, because a producer forging the broker's internal metadata
could impersonate a transaction it never opened. The size of
headers is bounded and counted against the record, because
unbounded headers are a payload smuggled past the value size
limit, and a limit with a hole beside it is not a limit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid

RESERVED_PREFIX = "__relay."
MAX_HEADER_BYTES = 4096


@dataclass
class Headers:
    entries: list[tuple[str, bytes]] = field(default_factory=list)

    def add(self, name: str, value: bytes) -> None:
        if not name.strip():
            raise Invalid("a header needs a name")
        if name.startswith(RESERVED_PREFIX):
            raise Invalid(
                f"{name} is in the reserved namespace "
                f"{RESERVED_PREFIX!r}; a producer forging broker "
                "metadata could impersonate a transaction it "
                "never opened"
            )
        if self.total_bytes() + len(name) + len(value) > MAX_HEADER_BYTES:
            raise Invalid(
                "headers exceed the size cap; unbounded headers "
                "are a payload smuggled past the value limit"
            )
        self.entries.append((name, value))

    def add_reserved(self, name: str, value: bytes) -> None:
        if not name.startswith(RESERVED_PREFIX):
            raise Invalid(
                "broker headers must use the reserved prefix"
            )
        self.entries.append((name, value))

    def get_all(self, name: str) -> list[bytes]:
        return [v for n, v in self.entries if n == name]

    def total_bytes(self) -> int:
        return sum(
            len(name) + len(value)
            for name, value in self.entries
        )

    def ordered_names(self) -> list[str]:
        return [name for name, _ in self.entries]
