"""Latency percentiles: the mean hides the tail that wakes people up.

Request latency is reported as an average by systems that have
not been paged yet. The average is nearly useless for a broker,
because the requests that matter are the slow ones, and a mean of
five milliseconds can hide a p99 of two seconds when one request
in a hundred stalls on a slow disk or a lock. The tracker keeps a
bounded histogram and reports percentiles, because p50, p99, and
p999 answer three different questions, the typical experience, the
bad-but-common experience, and the rare-but-catastrophic one, and
a service level objective is always written against a percentile,
never the mean. The tracker is honest about the cost of the tail:
it reports p99 next to the mean specifically so the gap is
visible, since a mean and a p99 that are close describe a healthy
system and a mean far below its p99 describes a system with a
hidden tail that a mean-only dashboard would call fine. The
histogram is bucketed rather than exact, trading a small
quantization error for bounded memory, and the report states the
bucket resolution, because a percentile precise to the
millisecond computed from ten-millisecond buckets is a false
precision that a careful operator should distrust.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class LatencyHistogram:
    bucket_ms: int
    counts: dict[int, int] = field(default_factory=dict)
    total: int = 0

    def __post_init__(self) -> None:
        if self.bucket_ms < 1:
            raise Invalid("bucket resolution must be positive")

    def observe(self, latency_ms: int) -> None:
        if latency_ms < 0:
            raise Invalid("latency cannot be negative")
        bucket = (latency_ms // self.bucket_ms) * self.bucket_ms
        self.counts[bucket] = self.counts.get(bucket, 0) + 1
        self.total += 1

    def percentile(self, p: float) -> int:
        if not 0 < p <= 100:
            raise Invalid("percentile is between 0 and 100")
        if self.total == 0:
            raise Invalid("no samples to compute a percentile")
        target = self.total * p / 100
        seen = 0
        for bucket in sorted(self.counts):
            seen += self.counts[bucket]
            if seen >= target:
                return bucket
        return max(self.counts)

    def mean(self) -> float:
        if self.total == 0:
            raise Invalid("no samples for a mean")
        weighted = sum(
            (bucket + self.bucket_ms / 2) * count
            for bucket, count in self.counts.items()
        )
        return weighted / self.total

    def report(self) -> str:
        mean = self.mean()
        p99 = self.percentile(99)
        gap = "healthy" if p99 <= mean * 3 else "hidden tail"
        return (
            f"mean {mean:.0f}ms, p50 {self.percentile(50)}ms, "
            f"p99 {p99}ms, p999 {self.percentile(99.9)}ms "
            f"({gap}, {self.bucket_ms}ms buckets); a mean far "
            "below its p99 is a tail a mean-only dashboard calls "
            "fine"
        )
