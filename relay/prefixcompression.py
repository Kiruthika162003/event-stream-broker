"""Prefix compression: sorted keys share a head, so store the head once.

Sorted string keys that share long common prefixes, topic names
under a convention, hierarchical keys, waste space storing the
prefix again in every key, and prefix compression removes the
waste: each key after the first stores only the length of the
prefix it shares with the previous key and its own differing
suffix. A run of keys like orders-2024-01, orders-2024-02,
orders-2024-03 stores the first in full and the rest as a shared
length and a two-character suffix, a large saving when the shared
head is long. This is the string analogue of the numeric delta
encoding: both exploit that sorted neighbors are close, delta by
subtraction for numbers and shared-prefix for strings, and both pay
off exactly when the data is sorted and clustered. Decoding walks
the entries, reconstructing each key by taking the shared prefix
length from the previous key and appending the stored suffix, an
exact round trip. The scheme depends on sorted input, because the
shared prefix with the previous key is only meaningful and only
long when the keys are in order, so the encoder refuses unsorted
input rather than producing short shared prefixes that store nearly
the whole key each and defeat the compression. It handles the first
key as a full store with a zero shared length, and it reports the
bytes saved against the raw, because keys with little in common
share short prefixes and compress little, and the ratio tells an
operator whether prefix compression is buying anything for this key
set or whether the keys are too dissimilar for it to help."
"""

from __future__ import annotations

from relay.errors import Invalid


def _shared_len(a: str, b: str) -> int:
    n = 0
    for ca, cb in zip(a, b, strict=False):
        if ca != cb:
            break
        n += 1
    return n


def encode(keys: list[str]) -> list[tuple[int, str]]:
    for i in range(1, len(keys)):
        if keys[i] < keys[i - 1]:
            raise Invalid(
                f"keys not sorted at position {i}; unsorted keys share short "
                "prefixes and defeat the compression"
            )
    out: list[tuple[int, str]] = []
    prev = ""
    for i, key in enumerate(keys):
        shared = 0 if i == 0 else _shared_len(prev, key)
        out.append((shared, key[shared:]))
        prev = key
    return out


def decode(entries: list[tuple[int, str]]) -> list[str]:
    out: list[str] = []
    prev = ""
    for shared, suffix in entries:
        if shared > len(prev):
            raise Invalid(
                f"shared length {shared} exceeds the previous key length "
                f"{len(prev)}; corruption in the encoded stream"
            )
        key = prev[:shared] + suffix
        out.append(key)
        prev = key
    return out


def compression_note(keys: list[str]) -> str:
    if not keys:
        return "no keys; nothing to encode"
    raw = sum(len(k) for k in keys)
    encoded = sum(len(suffix) for _, suffix in encode(keys))
    saved = raw - encoded
    return (
        f"raw {raw} char(s), suffixes {encoded}, saved {saved}; keys with "
        "little in common share short prefixes and save little, the ratio "
        "says whether prefix compression helps this key set"
    )
