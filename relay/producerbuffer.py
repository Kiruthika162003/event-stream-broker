"""Producer buffer: bounded accumulator memory, and what to do when it fills.

A producer accumulates records into batches in memory before
sending, which is how it batches and pipelines, and that memory
is bounded because unbounded producer memory is an out-of-memory
crash waiting for a slow broker. When the buffer fills, because
the broker is slower than the producer, there are two honest
policies and one dishonest one. Block: the send call waits until
buffer space frees, applying backpressure up into the
application, which is correct for a producer that must not lose
data and can afford to slow down. Fail: the send call returns an
error immediately, which is correct for a producer that would
rather drop a record than stall, a metrics emitter, a log
shipper. The dishonest policy is to silently drop the record and
return success, which turns a full buffer into invisible data
loss, and the buffer refuses to offer it. The block policy has a
timeout, because blocking forever is a hang, and a send that
blocks past its timeout fails rather than waiting indefinitely,
so even the patient policy has a bound. The report states how
long the producer spent blocked, because time blocked on the
buffer is backpressure the application felt, and a producer
blocked half its wall-clock is a producer whose broker cannot
keep up, a capacity signal the buffer is uniquely positioned to
see first.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

BLOCK = "block"
FAIL = "fail"
POLICIES = (BLOCK, FAIL)


@dataclass
class ProducerBuffer:
    capacity_bytes: int
    on_full: str
    block_timeout: int
    used_bytes: int = 0
    ticks_blocked: int = 0
    failed_sends: int = 0

    def __post_init__(self) -> None:
        if self.on_full not in POLICIES:
            raise Invalid(
                f"on-full must be {POLICIES}; silently dropping "
                "and returning success is invisible data loss "
                "and not on offer"
            )
        if self.capacity_bytes < 1:
            raise Invalid("the buffer needs capacity")

    def free(self, bytes_sent: int) -> None:
        self.used_bytes = max(0, self.used_bytes - bytes_sent)

    def append(
        self, size: int, free_in_ticks: int
    ) -> str:
        if self.used_bytes + size <= self.capacity_bytes:
            self.used_bytes += size
            return f"buffered {size} bytes"
        if self.on_full == FAIL:
            self.failed_sends += 1
            return (
                f"send failed: buffer full at "
                f"{self.capacity_bytes}, and this producer would "
                "rather drop than stall"
            )
        if free_in_ticks > self.block_timeout:
            self.failed_sends += 1
            self.ticks_blocked += self.block_timeout
            return (
                f"send failed after blocking {self.block_timeout} "
                "ticks: even the patient policy has a bound, "
                "because blocking forever is a hang"
            )
        self.ticks_blocked += free_in_ticks
        self.used_bytes += size
        return (
            f"blocked {free_in_ticks} tick(s) then buffered; the "
            "backpressure the application felt"
        )

    def report(self) -> str:
        return (
            f"{self.used_bytes} of {self.capacity_bytes} bytes "
            f"used, {self.ticks_blocked} tick(s) blocked, "
            f"{self.failed_sends} failed; time blocked is a "
            "capacity signal the buffer sees first"
        )
