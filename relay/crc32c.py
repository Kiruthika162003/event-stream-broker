"""CRC-32C: the checksum a batch carries, computed the way the wire expects.

Every record batch carries a CRC over its contents so a broker can
reject a batch corrupted in transit or on disk before it trusts a
single byte, and the polynomial is Castagnoli, not the older
CRC-32 of zip files, because Castagnoli detects more of the burst
errors that storage and networks actually produce. The computation
is table-driven: a 256-entry table is built once from the
polynomial, and each input byte indexes the table to fold eight
bits into the running remainder at a time, which is the standard
way to make a CRC fast without special hardware. The wire form
wraps the raw remainder in the usual pre- and post-conditioning,
an initial all-ones register and a final complement, because a
bare CRC cannot distinguish a message from the same message with
leading zero bytes prepended, and the conditioning removes that
blind spot. The verifier recomputes the CRC over the received
bytes and compares, and a mismatch means the batch is corrupt and
must be refused rather than appended, because appending a corrupt
batch would persist the corruption and serve it to every consumer.
The implementation refuses to verify against a stored CRC that is
not a 32-bit value, because a checksum field that overflowed its
width is itself evidence of corruption in the header, not a number
to compare against. The point of doing this in plain code rather
than trusting a library is that the broker must agree bit for bit
with producers and consumers on other runtimes, so the polynomial,
the conditioning, and the bit order are all pinned here explicitly.
"""

from __future__ import annotations

from relay.errors import Invalid

_POLY = 0x82F63B78
_MASK = 0xFFFFFFFF


def _build_table() -> tuple[int, ...]:
    table = []
    for n in range(256):
        crc = n
        for _ in range(8):
            crc = (crc >> 1) ^ _POLY if crc & 1 else crc >> 1
        table.append(crc & _MASK)
    return tuple(table)


_TABLE = _build_table()


def crc32c(data: bytes) -> int:
    crc = _MASK
    for byte in data:
        crc = _TABLE[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    return crc ^ _MASK


def verify(data: bytes, stored: int) -> bool:
    if not 0 <= stored <= _MASK:
        raise Invalid(
            "the stored CRC is not a 32-bit value; a checksum "
            "field that overflowed its width is itself evidence "
            "of a corrupt header, not a number to compare against"
        )
    return crc32c(data) == stored


def check_batch(data: bytes, stored: int) -> str:
    if verify(data, stored):
        return f"batch verified, crc 0x{stored:08x}"
    raise Invalid(
        f"batch crc mismatch: computed 0x{crc32c(data):08x} but "
        f"header says 0x{stored:08x}; the batch is corrupt and "
        "must be refused, not appended, or the corruption persists"
    )
