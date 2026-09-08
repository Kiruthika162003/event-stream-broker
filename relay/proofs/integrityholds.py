"""Flip any single byte and the checksum notices, every position.

The scenario is a batch corrupted by one flipped bit somewhere
in its payload, the kind of damage a bad cable or a failing
disk sector produces, and the claim is that the CRC catches it
no matter where the flip lands. The drill takes a payload,
computes its CRC-32C, then walks every byte position, flips the
low bit there, and checks that verification fails against the
original CRC. My first guess was that a checksum this short
might miss a flip in some unlucky position, since 32 bits
cannot uniquely fingerprint an arbitrary message. Measurement
corrected the guess for this case: a single-bit flip is exactly
what CRC is designed to always catch, and all positions were
detected, zero missed, because a one-bit change alters the
remainder deterministically. The counterfactual is a broker
that appended the corrupt batch anyway: it would persist the
damage and serve it to every consumer as if it were the
producer's data, so the gap between all-caught and any-missed
is the difference between rejecting corruption and laundering
it into the log.
"""

from __future__ import annotations

from relay.crc32c import crc32c, verify
from relay.proofs.finding import Finding


def run() -> Finding:
    payload = b"the-broker-must-agree-bit-for-bit-with-producers"
    good = crc32c(payload)
    positions = len(payload)
    missed = 0
    for i in range(positions):
        corrupt = bytearray(payload)
        corrupt[i] ^= 0x01
        if verify(bytes(corrupt), good):
            missed += 1
    numbers = {
        "positions_tested": positions,
        "flips_caught": positions - missed,
        "flips_missed": missed,
        "guess_was": "a 32-bit sum might miss some position",
        "measured": "single-bit flips are always caught",
    }
    holds = missed == 0
    return Finding(
        proof="integrityholds",
        claim=(
            "a single-bit flip in any of the payload's byte "
            "positions is caught by the CRC, none missed, so a "
            "corrupt batch is refused rather than laundered into "
            "the log"
        ),
        numbers=numbers,
        holds=holds,
    )
