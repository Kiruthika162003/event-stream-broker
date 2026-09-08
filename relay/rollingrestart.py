"""Rolling restart: one broker at a time, and never while redundancy is low.

Upgrading or reconfiguring a cluster means restarting every broker,
and doing it without downtime means one at a time, because each
broker holds replicas the cluster is counting toward its
replication factor, and restarting a broker takes its replicas
offline until it comes back and catches up. The rule that keeps the
restart safe is a wait: after restarting a broker, wait until every
partition it hosts is back in its full in-sync set before
restarting the next, because restarting the next while a partition
is still under-replicated from the last could take the partition
below its minimum in-sync count, or in the worst case offline, an
outage the rolling restart was meant to avoid. Skipping the wait is
the tempting shortcut under time pressure, restarting brokers back
to back to finish sooner, and it is exactly how a routine upgrade
turns into an incident. The coordinator tracks which brokers have
been restarted and, for the cluster, whether every partition is
fully in sync, and it permits the next restart only when no
partition is under-replicated. It refuses to restart the next
broker while any partition is still catching up from the previous
one, naming the lagging partitions so the operator waits for them
rather than forcing ahead, and refuses to restart a broker already
restarted in this pass, a bookkeeping slip that would skip one that
still needs it. It reports progress as brokers done against total
and whether the cluster is currently safe to proceed, because a
rolling restart that stalls is usually one partition slow to catch
up, and naming it turns an opaque wait into a specific thing to
watch rather than a reason to skip the wait.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class RollingRestart:
    brokers: list[str]
    restarted: set[str] = field(default_factory=set)
    under_replicated: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not self.brokers:
            raise Invalid("no brokers to restart")

    def safe_to_proceed(self) -> bool:
        return not self.under_replicated

    def restart(self, broker: str) -> str:
        if broker not in self.brokers:
            raise Invalid(f"'{broker}' is not in the cluster")
        if broker in self.restarted:
            raise Invalid(
                f"'{broker}' was already restarted this pass; a slip that "
                "would skip one still needing it"
            )
        if self.under_replicated:
            raise Invalid(
                f"partitions {sorted(self.under_replicated)} are still under-"
                "replicated from the last restart; restarting now could take "
                "one below its minimum in-sync count, wait for them"
            )
        self.restarted.add(broker)
        return f"restarted '{broker}'; wait for its partitions to rejoin the ISR"

    def catch_up(self, partition: str) -> None:
        self.under_replicated.discard(partition)

    def mark_under_replicated(self, partition: str) -> None:
        self.under_replicated.add(partition)

    def progress(self) -> str:
        done = len(self.restarted)
        state = "safe to proceed" if self.safe_to_proceed() else (
            f"waiting on {sorted(self.under_replicated)}"
        )
        return f"{done}/{len(self.brokers)} brokers restarted; {state}"
