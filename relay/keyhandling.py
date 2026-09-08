"""Null keys and empty keys are different, and conflating them loses order.

A record's key decides its partition and, on a compacted topic,
its identity, so how the broker treats keys is more consequential
than it looks. The distinction that trips up every naive
implementation is null versus empty. A null key means the
producer expressed no key, so the record round-robins or sticks
for balance and has no per-key ordering guarantee. An empty key,
a present key of zero length, is a real key whose value happens
to be empty, so it hashes like any key and all empty-keyed
records land in one partition in order, which is exactly what a
producer keying by a field that is sometimes blank intends.
Collapsing the two, treating empty as null, scatters records the
producer meant to keep together, and the bug is invisible until
someone keys by a field that is empty for a meaningful subset and
watches their ordering dissolve. On a compacted topic the
distinction sharpens further: a null-keyed record cannot be
compacted because compaction needs a key to dedup by, so a
producer sending null keys to a compacted topic is making a
category error the broker should catch, and a tombstone, a record
with a null value, is the delete marker that must be keyed,
because a delete of nothing in particular deletes nothing.
"""

from __future__ import annotations

import hashlib

from relay.errors import Invalid


def partition_for_key(
    key: bytes | None, partitions: int, round_robin_next: int
) -> tuple[int, str]:
    if partitions < 1:
        raise Invalid("need at least one partition")
    if key is None:
        return round_robin_next % partitions, (
            "null key: no per-key order, round-robin for balance"
        )
    digest = hashlib.sha256(key).hexdigest()
    slot = int(digest[:8], 16) % partitions
    descriptor = (
        "empty key: a real zero-length key, hashed and ordered"
        if key == b""
        else "keyed: hashed to a stable home partition"
    )
    return slot, descriptor


def validate_for_compacted(
    key: bytes | None, value: bytes | None
) -> str:
    if key is None:
        raise Invalid(
            "a null-keyed record cannot go to a compacted topic; "
            "compaction needs a key to dedup by, and a null key "
            "is a category error the broker catches"
        )
    if value is None:
        return (
            f"tombstone for key {key!r}: a keyed delete marker, "
            "because a delete of nothing in particular deletes "
            "nothing"
        )
    return f"compactable record for key {key!r}"


def keys_land_together(
    key_a: bytes | None, key_b: bytes | None, partitions: int
) -> bool:
    if key_a is None or key_b is None:
        return False
    slot_a, _ = partition_for_key(key_a, partitions, 0)
    slot_b, _ = partition_for_key(key_b, partitions, 0)
    return slot_a == slot_b
