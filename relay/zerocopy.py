"""Zero copy: the broker ships bytes disk-to-socket without touching them.

A broker serving a fetch normally moves the segment's bytes from
the page cache straight to the network socket without copying them
into its own memory or looking at them, using the operating
system's sendfile path, which is the single biggest reason a broker
can serve so much throughput per core: the data never enters user
space, so the broker spends almost no CPU per byte served. The
zero-copy path holds only while the broker does not need to
transform the bytes, and two things force it to give up. The first
is down-conversion: a consumer too old to understand the stored
record format needs the batch rewritten into an older format, which
the broker cannot do without reading the bytes into user space,
copying, transforming, and only then sending, so an old consumer
turns a cheap zero-copy fetch into an expensive one and raises CPU
for everyone. The second is encryption in transit: TLS must
encrypt the bytes before they hit the socket, which also requires
them in user space, so a broker serving over TLS pays a copy that a
plaintext broker does not. The model decides whether a fetch can
take the zero-copy path and estimates the CPU multiple when it
cannot, so an operator sees that a spike in broker CPU tracks a
population of old consumers forcing conversion rather than a rise
in traffic. The model refuses to claim zero-copy for a fetch that
needs conversion, because reporting a converted fetch as zero-copy
would hide exactly the CPU cost the operator is trying to find.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class FetchPath:
    needs_downconversion: bool
    needs_encryption: bool
    convert_cpu_multiple: float = 8.0

    def __post_init__(self) -> None:
        if self.convert_cpu_multiple < 1:
            raise Invalid(
                "conversion cannot cost less than zero-copy; the "
                "multiple is at least one"
            )

    def is_zero_copy(self) -> bool:
        return not self.needs_downconversion and not self.needs_encryption

    def cpu_multiple(self) -> float:
        if self.is_zero_copy():
            return 1.0
        if self.needs_downconversion:
            return self.convert_cpu_multiple
        return 2.0

    def classify(self) -> str:
        if self.is_zero_copy():
            return (
                "zero-copy: disk to socket untouched, almost no CPU "
                "per byte, the broker's throughput secret"
            )
        if self.needs_downconversion:
            return (
                f"down-conversion forces bytes into user space: "
                f"~{self.cpu_multiple():.0f}x the CPU, so an old "
                "consumer raises CPU for everyone, not a traffic rise"
            )
        return (
            "TLS must encrypt before the socket: bytes copied into "
            "user space, ~2x the CPU a plaintext broker pays"
        )
