"""A wire-format day: encode small, checksum honest, derive offsets from a base.

Run with: python -m examples.wireformatday
"""

from __future__ import annotations

from relay.batchheader import BatchHeader
from relay.crc32c import check_batch, crc32c
from relay.varint import decode_varint, encode_varint


def morning_small_deltas_cost_little():
    deltas = [0, 1, 2, -1, 300, -300]
    encoded = b"".join(encode_varint(d) for d in deltas)
    print(
        f"morning: {len(deltas)} deltas encoded in {len(encoded)} "
        "byte(s); a small negative costs what a small positive does"
    )
    decoded = []
    buf = encoded
    while buf:
        value, consumed = decode_varint(buf)
        decoded.append(value)
        buf = buf[consumed:]
    print(f"         decoded back to {decoded}, round-trip exact")


def noon_the_checksum_catches_the_flip():
    payload = b"orders-partition-3-batch-0007"
    crc = crc32c(payload)
    print(f"noon:    batch crc 0x{crc:08x}; {check_batch(payload, crc)}")
    corrupt = bytearray(payload)
    corrupt[10] ^= 0x01
    try:
        check_batch(bytes(corrupt), crc)
    except Exception as caught:
        print(f"         one bit flipped: {caught}")


def afternoon_offsets_from_a_base():
    header = BatchHeader(
        base_offset=1000,
        last_offset_delta=4,
        base_timestamp=1_700_000_000,
        record_count=3,
    )
    print(
        f"afternoon: batch at base {header.base_offset}, record 2 "
        f"is offset {header.offset_of(2)}, next base "
        f"{header.next_base_offset()}"
    )
    print(f"           {header.coverage()}")


def main() -> int:
    morning_small_deltas_cost_little()
    noon_the_checksum_catches_the_flip()
    afternoon_offsets_from_a_base()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
