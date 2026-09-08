"""Partition expansion: adding partitions is easy, or it breaks every key.

A topic can grow its partition count, and whether that is safe
depends entirely on one property that is easy to overlook. For an
unkeyed topic, adding partitions just gives the producer more
places to round-robin, no existing record moves, and the change
is transparent. For a keyed topic, adding partitions changes the
hash modulus, so keys that hashed to partition three under the
old count now hash somewhere else under the new one, which means
a key's records are split across two partitions, the old ones
where they landed before and the new ones after, and per-key
order, the guarantee keyed topics exist to provide, is broken for
every key from the moment of expansion. The expander refuses to
add partitions to a keyed topic in place, because the operation
looks like a simple config change and silently destroys ordering,
the worst kind of footgun. The safe path it offers instead is
explicit: create a new topic with the desired partition count and
migrate, republishing records so each key lands consistently, the
same work the naive expansion pretended to avoid but done without
breaking the guarantee. The expander also handles the subtle case
of a topic that is nominally keyed but has only ever received
null keys, which behaves like an unkeyed topic and can expand
safely, but it requires the operator to assert that no keyed
records will ever arrive, because an expansion that is safe only
as long as nobody uses keys is a landmine with a note on it.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class ExpansionRequest:
    topic: str
    keyed: bool
    current_partitions: int
    new_partitions: int

    def __post_init__(self) -> None:
        if self.new_partitions <= self.current_partitions:
            raise Invalid(
                "expansion must increase the partition count"
            )


def evaluate_expansion(
    request: ExpansionRequest,
    operator_asserts_no_keys: bool = False,
) -> str:
    if not request.keyed:
        return (
            f"{request.topic}: safe to expand "
            f"{request.current_partitions} -> "
            f"{request.new_partitions}; unkeyed records just get "
            "more round-robin targets, nothing moves"
        )
    if operator_asserts_no_keys:
        return (
            f"{request.topic}: expanding under an operator "
            "assertion that no keyed records will ever arrive; a "
            "landmine with a note on it, but permitted"
        )
    raise Invalid(
        f"{request.topic} is keyed: expanding "
        f"{request.current_partitions} -> {request.new_partitions} "
        "changes the hash modulus, splitting every key across old "
        "and new partitions and breaking per-key order; create a "
        "new topic and migrate, the same work done without "
        "breaking the guarantee"
    )


def keys_would_split(
    key_hash: int, old_count: int, new_count: int
) -> bool:
    return (key_hash % old_count) != (key_hash % new_count)
