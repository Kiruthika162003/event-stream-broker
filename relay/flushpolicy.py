"""Flush policy: when bytes go from the OS page cache to the actual disk.

A record written to a log is in the OS page cache immediately but
on the physical disk only after an fsync, and the gap between
those two is a durability question most brokers answer by not
thinking about it. Flushing on every record is maximally durable
and slow, because fsync is expensive and doing it per record
caps throughput at the disk's sync rate. Flushing never trusts
the OS to write eventually, which is fast and loses everything in
the page cache on a power failure. The policy the broker actually
relies on is subtler: it does not flush aggressively, because it
achieves durability through replication instead, a record
acknowledged by the in-sync set survives any single machine's
power failure whether or not that machine fsynced, so the flush
can be lazy and the durability comes from copies, not from disk
syncs. This is the insight that makes the broker fast: fsync is
traded for replication, and a cluster with replication factor
three does not need per-record fsync because two other machines
hold the record. The policy the checker enforces is the dangerous
combination it forbids: replication factor one with lazy flush,
because that configuration has neither durability mechanism, no
copies and no syncs, so an acknowledged record lives only in one
machine's page cache and a power failure loses acknowledged data,
the promise the broker must never break. The report states which
mechanism provides durability, because an operator who thinks
fsync protects them while running lazy flush is protected by
replication they might be about to reduce.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

EVERY_RECORD = "every-record"
INTERVAL = "interval"
LAZY = "lazy"
POLICIES = (EVERY_RECORD, INTERVAL, LAZY)


@dataclass(frozen=True)
class DurabilityConfig:
    flush_policy: str
    replication_factor: int

    def __post_init__(self) -> None:
        if self.flush_policy not in POLICIES:
            raise Invalid(f"unknown flush policy {self.flush_policy}")
        if self.replication_factor < 1:
            raise Invalid("replication factor must be positive")


def durability_source(config: DurabilityConfig) -> str:
    fsync_durable = config.flush_policy == EVERY_RECORD
    replication_durable = config.replication_factor >= 2
    if not fsync_durable and not replication_durable:
        raise Invalid(
            "replication factor 1 with lazy flush has neither "
            "durability mechanism: no copies and no syncs, so an "
            "acknowledged record lives in one page cache and a "
            "power failure loses acknowledged data"
        )
    if replication_durable and not fsync_durable:
        return (
            f"durability from replication (factor "
            f"{config.replication_factor}): fsync traded for "
            "copies, and this is what makes the broker fast"
        )
    if fsync_durable and not replication_durable:
        return (
            "durability from fsync alone: every record synced, "
            "slow but safe on a single machine"
        )
    return (
        "durability from both replication and fsync: safe and "
        "slow, belt and suspenders"
    )


def throughput_note(config: DurabilityConfig) -> str:
    if config.flush_policy == EVERY_RECORD:
        return "throughput capped at the disk sync rate"
    return "throughput unbound by fsync; the page cache absorbs writes"
