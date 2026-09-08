"""Hot partition: one partition taking far more than its share, and why.

Partitions are meant to spread load evenly, so each takes roughly
its share of the traffic, and a partition taking far more than that
is a hot partition, a bottleneck that limits throughput to what one
partition and one consumer can handle no matter how many partitions
the topic has. The cause is almost always a skewed key: records are
placed by hashing the key, so an even spread needs many keys of
similar volume, and a single dominant key, one customer producing
most of the events, or a null-key fallback that pins everything to
one partition, sends its whole volume to one partition. The
detector computes each partition's share of the traffic and flags
one whose share is a large multiple of the even share, the even
share being one over the partition count. What matters most is the
fix it implies, because the obvious fix, add more partitions, does
not help when one key dominates: that key still hashes to one
partition, so its volume still lands there, and the new partitions
sit idle. The real fix is a better key, splitting the dominant key
into sub-keys, or a custom partitioner, so the detector names the
skewed distribution rather than suggesting more partitions that
would not move the hot key. It refuses to flag a partition merely
above the even share, since random variation puts some above it,
using a multiple as the threshold. It reports the hottest
partition's share against the even share, because a partition at
twice its share is mild skew to watch while one at ten times is a
single key that has effectively serialized the topic onto one
partition, a different severity and the same root cause."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class HotPartitionDetector:
    counts: dict[int, int] = field(default_factory=dict)
    multiple: float = 3.0

    def __post_init__(self) -> None:
        if self.multiple <= 1:
            raise Invalid("the hot multiple must exceed one; the even share is not hot")

    def total(self) -> int:
        return sum(self.counts.values())

    def even_share(self) -> float:
        if not self.counts:
            return 0.0
        return self.total() / len(self.counts)

    def hot_partitions(self) -> list[int]:
        even = self.even_share()
        if even == 0:
            return []
        return [p for p, c in self.counts.items() if c >= even * self.multiple]

    def report(self) -> str:
        if not self.counts:
            return "no traffic observed"
        hottest = max(self.counts, key=self.counts.get)
        ratio = self.counts[hottest] / self.even_share()
        if hottest not in self.hot_partitions():
            return f"partition {hottest} at {ratio:.1f}x the even share; balanced enough"
        return (
            f"partition {hottest} at {ratio:.1f}x the even share, a hot "
            "partition from a skewed key; the fix is a better key or "
            "partitioner, not more partitions the hot key would still skip"
        )
