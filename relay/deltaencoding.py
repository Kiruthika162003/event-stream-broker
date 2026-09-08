"""Delta encoding: store the gaps between sorted values, not the values.

A sorted sequence of large numbers, the offsets or timestamps in an
index, compresses well if you store not each value but the gap from
the previous one, because the gaps are small even when the values
are large: a run of offsets a few apart stores as a base and a
string of small deltas rather than a string of eight-byte absolutes.
This pairs with the varint encoding elsewhere, small deltas cost one
byte each while the absolutes would cost eight, so a delta-encoded
index of a thousand entries a few apart is a fraction of the size of
the raw one, which matters because the index is memory-mapped and
smaller means more of it stays in cache. Decoding is the exact
inverse: start at the base and add each delta in turn to
reconstruct the originals, and the round trip is lossless. The
scheme relies on the input being sorted, because a delta from a
larger to a smaller value is negative and a negative delta is both
larger to encode and a sign the sequence was not sorted, so the
encoder refuses a non-increasing input rather than producing a
delta stream that is bigger than the raw and wrong to decode as
gaps. It stores the first value as the base absolute and the rest as
deltas, so an empty sequence encodes to nothing and a single value
to just its base. It reports the compression the deltas achieve
against the raw size, because a sequence whose deltas are large, values
far apart, compresses little, and the ratio tells an operator
whether delta encoding is buying anything for this particular index
or whether the values are too spread for it to help."
"""

from __future__ import annotations

from relay.errors import Invalid


def encode(values: list[int]) -> list[int]:
    if not values:
        return []
    for i in range(1, len(values)):
        if values[i] < values[i - 1]:
            raise Invalid(
                f"input not sorted at position {i} ({values[i]} < "
                f"{values[i - 1]}); a negative delta is bigger to encode and "
                "wrong to decode as a gap"
            )
    out = [values[0]]
    for i in range(1, len(values)):
        out.append(values[i] - values[i - 1])
    return out


def decode(deltas: list[int]) -> list[int]:
    if not deltas:
        return []
    out = [deltas[0]]
    for d in deltas[1:]:
        out.append(out[-1] + d)
    return out


def compression_note(values: list[int]) -> str:
    if not values:
        return "empty sequence; nothing to encode"
    deltas = encode(values)
    # a crude proxy: bytes are ~ number of decimal digits
    raw = sum(len(str(v)) for v in values)
    encoded = sum(len(str(d)) for d in deltas)
    saved = raw - encoded
    return (
        f"raw ~{raw} digit(s), delta-encoded ~{encoded}, saved ~{saved}; "
        "values far apart give large deltas and little saving, the ratio "
        "says whether delta encoding buys anything here"
    )
