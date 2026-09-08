"""Chop the stream anywhere, the frames come back identical.

The scenario is a socket that delivers the same bytes in wildly
different chunk boundaries on different runs, one byte at a time
here, one giant read there, and the claim is that the reader
reassembles the exact same sequence of frames regardless of where
the chunks were split. The drill encodes three frames into one
byte string, then feeds that string to a fresh reader at every
possible single split point and also one byte at a time, collecting
the frames each way. My first guess was that a split landing inside
the four-byte length header might trip the reader, since it reads
the length before it has all four bytes. Measurement corrected the
guess: every split point and the one-byte-at-a-time feed produced
the identical three frames, because the reader yields nothing until
it holds a whole header and a whole payload, so a split inside the
header just waits for the rest. The counterfactual is a reader that
acted on a partial header: it would read a garbage length from the
bytes it had and either reject a valid stream or try to allocate
against nonsense, so the gap between all-splits-agree and any-split-
differs is the difference between a reader that survives real
sockets and one that only works when reads happen to align with
frames.
"""

from __future__ import annotations

from relay.framing import FrameReader
from relay.proofs.finding import Finding

_MAX = 4096


def _encode(payloads: list[bytes]) -> bytes:
    return b"".join(len(p).to_bytes(4, "big") + p for p in payloads)


def run() -> Finding:
    payloads = [b"alpha", b"", b"a-longer-payload-here"]
    stream = _encode(payloads)
    baseline = FrameReader(max_size=_MAX).feed(stream)

    disagreements = 0
    for split in range(1, len(stream)):
        reader = FrameReader(max_size=_MAX)
        got = reader.feed(stream[:split]) + reader.feed(stream[split:])
        if got != baseline:
            disagreements += 1

    one_at_a_time = FrameReader(max_size=_MAX)
    drip: list[bytes] = []
    for i in range(len(stream)):
        drip.extend(one_at_a_time.feed(stream[i : i + 1]))

    numbers = {
        "split_points_tested": len(stream) - 1,
        "disagreements": disagreements,
        "drip_matches": drip == baseline,
        "guess_was": "a split inside the length header might trip it",
        "measured": "every split and the one-byte drip agree",
    }
    holds = (
        disagreements == 0
        and drip == baseline
        and baseline == payloads
    )
    return Finding(
        proof="framingholds",
        claim=(
            "the frame reader reassembles the identical frames at "
            "every chunk boundary and one byte at a time, so it "
            "survives a real socket instead of only aligned reads"
        ),
        numbers=numbers,
        holds=holds,
    )
