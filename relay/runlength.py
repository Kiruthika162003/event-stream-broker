"""Run length: a run of the same value becomes one value and a count.

Some data a broker holds runs in stretches of the same value: a
batch of records all with the same key, a span of control records,
a header field constant across a batch, and run-length encoding
compresses exactly that by replacing a run of N identical values
with the value and the count N. A thousand records of one key store
as one pair instead of a thousand copies, a large saving when the
data is runny. The catch is the opposite case: data with no runs,
every value different from the next, encodes to a pair per value,
which is larger than the raw because each value now also carries a
count of one, so run-length encoding helps runny data and hurts
random data, and applying it blindly to the wrong data inflates
rather than compresses. The encoder walks the sequence, emitting a
value and a run count each time the value changes, and the decoder
expands each pair back, a lossless round trip. It refuses a
non-positive run count on decode, which cannot describe a run and
is corruption in the encoded stream, and it reports whether the
encoding actually shrank the data, because a negative saving means
the data was not runny and the encoding should not have been
applied, the honest measure that stops run-length encoding from
being used where it makes things worse. The report states the run
count against the value count, because a sequence encoding to
nearly as many runs as values is random data the encoding cannot
help, visible in the ratio before it shows up as a store that grew."
"""

from __future__ import annotations

from relay.errors import Invalid


def encode(values: list[int]) -> list[tuple[int, int]]:
    if not values:
        return []
    out: list[tuple[int, int]] = []
    current = values[0]
    count = 1
    for v in values[1:]:
        if v == current:
            count += 1
        else:
            out.append((current, count))
            current = v
            count = 1
    out.append((current, count))
    return out


def decode(runs: list[tuple[int, int]]) -> list[int]:
    out: list[int] = []
    for value, count in runs:
        if count < 1:
            raise Invalid(
                f"run count {count} cannot describe a run; corruption in the "
                "encoded stream"
            )
        out.extend([value] * count)
    return out


def compression_note(values: list[int]) -> str:
    if not values:
        return "empty sequence; nothing to encode"
    runs = encode(values)
    saved = len(values) - len(runs)
    if saved <= 0:
        return (
            f"{len(values)} value(s) encoded to {len(runs)} run(s); no saving, "
            "the data was not runny and run-length encoding should not have "
            "been applied here"
        )
    return (
        f"{len(values)} value(s) compressed to {len(runs)} run(s), saved "
        f"{saved}; runny data, the encoding earns its place"
    )
