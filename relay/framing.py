"""Framing: a request is a length then that many bytes, and the length is suspect.

Requests arrive on a stream socket as a sequence of bytes with no
inherent boundaries, so the protocol frames each request as a four-
byte big-endian length followed by exactly that many payload bytes,
and the reader's job is to carve the stream back into requests. Two
things make this more than a loop. The first is partial reads: a
socket read returns whatever bytes have arrived, which may be less
than a full frame or may straddle two frames, so the reader buffers
what it has and yields a request only once the buffer holds the
whole payload the length promised, keeping any leftover bytes for
the next frame. The second is the length being hostile: the length
is the first thing read and the least trustworthy, because a
corrupt or malicious peer can send a length claiming gigabytes, and
a reader that allocated a buffer of the claimed size before
checking would let one bad length exhaust the broker's memory. So
the reader checks the length against the configured maximum request
size before allocating anything, and rejects a frame whose length
exceeds it as a protocol violation, tearing down the connection
rather than trying to read a request that cannot be legitimate. The
reader refuses a negative length outright, which a signed four-byte
field can carry and which would otherwise be read as an enormous
unsigned size, and it treats a zero length as a valid empty frame
rather than an error, because some requests carry no payload. The
report states how many bytes are buffered but not yet a full frame,
because a connection stalled with a partial frame is either a slow
client or one that sent a length larger than the data it followed
with, a mismatch worth catching.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid

_HEADER = 4


@dataclass
class FrameReader:
    max_size: int
    buffer: bytearray = field(default_factory=bytearray)

    def __post_init__(self) -> None:
        if self.max_size < 1:
            raise Invalid("the max request size must be positive")

    def feed(self, chunk: bytes) -> list[bytes]:
        self.buffer.extend(chunk)
        frames: list[bytes] = []
        while True:
            if len(self.buffer) < _HEADER:
                break
            length = int.from_bytes(self.buffer[:_HEADER], "big", signed=True)
            if length < 0:
                raise Invalid(
                    "a negative frame length is corruption; a signed "
                    "field carrying it would read as an enormous size"
                )
            if length > self.max_size:
                raise Invalid(
                    f"frame length {length} exceeds the max request "
                    f"size {self.max_size}; refusing before allocating, "
                    "or one bad length exhausts memory"
                )
            if len(self.buffer) - _HEADER < length:
                break
            frames.append(bytes(self.buffer[_HEADER : _HEADER + length]))
            del self.buffer[: _HEADER + length]
        return frames

    def pending(self) -> str:
        held = len(self.buffer)
        return (
            f"{held} byte(s) buffered without a full frame; a stall "
            "here is a slow client or a length larger than the data "
            "that followed it"
        )
