"""Records: the unit of delivery, immutable and self-checking.

A record is bytes with a passport: an optional key that decides
its partition, a value, headers for the metadata that is about
the delivery rather than in it, and a checksum computed at
construction, because corruption discovered at consume time is
corruption with a suspect list a mile long, while corruption
discovered at append time has exactly one. Records never carry
wall-clock timestamps here; the log's own offsets are the only
order this broker promises, and stamping records with the
producer's clock would smuggle in a second ordering that
disagrees with the first on every machine with clock drift,
which is every machine.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from relay.errors import Invalid

MAX_VALUE_BYTES = 1_000_000


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()[:16]


@dataclass(frozen=True)
class Record:
    value: bytes
    key: bytes | None = None
    headers: tuple[tuple[str, str], ...] = ()
    checksum: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        if not self.value:
            raise Invalid(
                "an empty value is a heartbeat, not a record; "
                "heartbeats have their own channel"
            )
        if len(self.value) > MAX_VALUE_BYTES:
            raise Invalid(
                f"value of {len(self.value)} bytes exceeds the "
                f"{MAX_VALUE_BYTES} cap; ship a pointer, not "
                "the payload"
            )
        for name, _ in self.headers:
            if not name.strip():
                raise Invalid("headers need names")
        object.__setattr__(
            self, "checksum", self.body_digest()
        )

    def body_digest(self) -> str:
        parts = [self.value, self.key or b""]
        for name, value in self.headers:
            parts.append(name.encode())
            parts.append(value.encode())
        return _digest(b"|".join(parts))

    def verify(self) -> None:
        if self.checksum != self.body_digest():
            raise Invalid(
                "checksum mismatch: the record changed between "
                "construction and now, and exactly one suspect "
                "had custody"
            )

    def size_bytes(self) -> int:
        header_bytes = sum(
            len(name) + len(value)
            for name, value in self.headers
        )
        return (
            len(self.value)
            + len(self.key or b"")
            + header_bytes
        )
