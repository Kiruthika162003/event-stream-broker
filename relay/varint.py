"""Varint: small numbers cost few bytes, and negatives do not cost the most.

The record format encodes lengths and offsets as variable-length
integers rather than fixed four- or eight-byte fields, because most
of these numbers are small, a short key length or a low offset
delta, and a varint spends one byte on a small number instead of
eight. The encoding puts seven bits of value in each byte and uses
the eighth as a continuation flag, so a reader knows to keep
reading while the high bit is set and to stop at the first byte
without it. A naive varint has a flaw for signed values: a small
negative like minus one has all its high bits set in two's
complement, so it would encode to the maximum width, the worst
case for a number that is small in magnitude. Zigzag fixes that by
mapping signed to unsigned so that numbers small in absolute value
map to small unsigned values regardless of sign: zero to zero,
minus one to one, one to two, minus two to three, so a small
negative costs as little as a small positive. The decoder is the
exact inverse, and the pair round-trips every value, which the
tests check across a range that crosses zero. The reader refuses a
varint that never terminates within the width its type allows,
because a stream of continuation bytes with no stop is either
corruption or a hostile input trying to make the reader loop, and
a length prefix that does not terminate cannot be trusted to bound
anything. The point of pinning this here is the same as the
checksum: the broker must decode exactly what other runtimes
encoded, so the bit layout is explicit, not delegated.
"""

from __future__ import annotations

from relay.errors import Invalid

_CONTINUE = 0x80
_MASK = 0x7F
_MAX_BYTES = 10


def zigzag_encode(value: int) -> int:
    return (value << 1) ^ (value >> 63) if value < 0 else value << 1


def zigzag_decode(value: int) -> int:
    return (value >> 1) ^ -(value & 1)


def encode_varint(value: int) -> bytes:
    n = zigzag_encode(value)
    out = bytearray()
    while True:
        byte = n & _MASK
        n >>= 7
        if n:
            out.append(byte | _CONTINUE)
        else:
            out.append(byte)
            return bytes(out)


def decode_varint(data: bytes) -> tuple[int, int]:
    result = 0
    shift = 0
    for i, byte in enumerate(data):
        if i >= _MAX_BYTES:
            raise Invalid(
                "varint did not terminate within its width; a "
                "length prefix that never stops is corruption or a "
                "hostile input trying to make the reader loop"
            )
        result |= (byte & _MASK) << shift
        if not byte & _CONTINUE:
            return zigzag_decode(result), i + 1
        shift += 7
    raise Invalid(
        "varint ran off the end of the buffer with the "
        "continuation bit still set; the input is truncated"
    )
