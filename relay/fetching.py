"""Fetching: wait a little to send a lot, but never wait past the promise.

A consumer that fetches one record per round trip spends all its
time on network overhead; a consumer that waits for a full batch
adds latency to every record. The fetch planner sits between:
the consumer names a min-bytes it wants and a max-wait it will
tolerate, and the broker holds the response until either enough
bytes have accumulated or the wait expires, whichever comes
first. The whichever-comes-first is the entire contract, because
a broker that honored only min-bytes would hang a low-traffic
partition forever waiting for bytes that never come, and one
that honored only max-wait would never batch. The max-bytes
ceiling is the third bound, protecting the consumer from a
response too large to hold, and a single record larger than
max-bytes is still returned alone rather than starving the
consumer forever on a record it can never fit, because
progress on an awkward record beats deadlock on principle.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class FetchRequest:
    min_bytes: int
    max_bytes: int
    max_wait_ticks: int

    def __post_init__(self) -> None:
        if self.min_bytes < 0 or self.max_bytes < 1:
            raise Invalid(
                "min-bytes is nonnegative and max-bytes positive"
            )
        if self.min_bytes > self.max_bytes:
            raise Invalid(
                "min-bytes above max-bytes can never be "
                "satisfied within the ceiling"
            )
        if self.max_wait_ticks < 0:
            raise Invalid("max-wait cannot be negative")


@dataclass
class FetchResult:
    records_returned: int
    bytes_returned: int
    reason: str


def plan_fetch(
    request: FetchRequest,
    available_sizes: list[int],
    now_wait: int,
) -> FetchResult:
    batch: list[int] = []
    total = 0
    for size in available_sizes:
        if batch and total + size > request.max_bytes:
            break
        batch.append(size)
        total += size
        if size > request.max_bytes:
            return FetchResult(
                records_returned=1,
                bytes_returned=size,
                reason=(
                    "single record exceeds max-bytes, returned "
                    "alone because progress on an awkward record "
                    "beats deadlock on principle"
                ),
            )
        if total >= request.min_bytes:
            return FetchResult(
                records_returned=len(batch),
                bytes_returned=total,
                reason="min-bytes reached, sent immediately",
            )
    if now_wait >= request.max_wait_ticks:
        return FetchResult(
            records_returned=len(batch),
            bytes_returned=total,
            reason=(
                f"max-wait of {request.max_wait_ticks} expired "
                "with a partial batch, sent so a quiet partition "
                "never hangs"
            ),
        )
    return FetchResult(
        records_returned=0,
        bytes_returned=0,
        reason=(
            f"holding: {total} of {request.min_bytes} bytes, "
            f"{request.max_wait_ticks - now_wait} tick(s) of "
            "patience left"
        ),
    )
