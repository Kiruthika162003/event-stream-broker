"""Slow broker: the one still alive but dragging, worse than the one that died.

A dead broker is handled well: it misses heartbeats, gets fenced,
its partitions fail over, and the cluster moves on. A slow broker
is harder, because it is still alive, still heartbeating, still in
the in-sync set, but serving everything late, and that is worse
than dead in one specific way: as long as it stays in the in-sync
set, produce with acks-all waits for it, so its slowness becomes
every acks-all producer's latency on every partition it follows,
and nothing fails it over because from the liveness check's point
of view it is fine. This is the gray failure that liveness misses,
a broker degraded but not down, and catching it needs a different
signal than heartbeats: elevated latency and a fetch rate that has
fallen well below its peers while it is still nominally healthy.
The detector compares a broker's latency and replication pace
against the fleet, and flags one that is a large multiple slower
than the median as a slow broker, a candidate to remove from the
in-sync set deliberately so produce stops waiting for it, trading
its redundancy for the latency of the many producers it is holding
up. The detector refuses to flag a broker merely above the median,
because half the fleet is always above the median and flagging them
would remove healthy brokers, so the threshold is a multiple, not a
rank. It distinguishes a uniformly slow fleet, where every broker is
slow together and the problem is load not one broker, from one
broker slow against fast peers, because removing a broker helps only
in the second case. It reports the slow broker's multiple over the
median, because a broker two times the median is a watch while one
ten times is a remove, and the multiple, not the raw latency, is
what decides.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class SlowBrokerDetector:
    latencies: dict[str, float] = field(default_factory=dict)
    multiple: float = 3.0

    def __post_init__(self) -> None:
        if self.multiple <= 1:
            raise Invalid("the slow multiple must exceed one; the median is not slow")

    def _median(self) -> float:
        vals = sorted(self.latencies.values())
        n = len(vals)
        if n == 0:
            raise Invalid("no brokers observed")
        mid = n // 2
        if n % 2:
            return vals[mid]
        return (vals[mid - 1] + vals[mid]) / 2

    def slow_brokers(self) -> list[str]:
        if len(self.latencies) < 2:
            return []
        median = self._median()
        if median == 0:
            return []
        return [
            b
            for b, lat in self.latencies.items()
            if lat >= median * self.multiple
        ]

    def report(self, broker: str) -> str:
        median = self._median()
        lat = self.latencies.get(broker)
        if lat is None:
            raise Invalid(f"no observation for '{broker}'")
        ratio = lat / median if median else 0
        if broker not in self.slow_brokers():
            return f"'{broker}' at {ratio:.1f}x the median; within the fleet"
        verdict = "watch" if ratio < 5 else "remove from the in-sync set"
        return (
            f"'{broker}' is {ratio:.1f}x the median, a slow broker holding up "
            f"every acks-all producer that waits for it: {verdict}"
        )
