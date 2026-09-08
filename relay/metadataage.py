"""Metadata age: stale routing is fine to read with, dangerous to write with.

A client caches metadata and the cache ages, and how much staleness
is tolerable depends on what the client is about to do with it. For
a read, mildly stale metadata is fine: the worst case is a fetch to
a broker that just stopped being the leader, which returns
not-leader and triggers a refresh, self-correcting cheaply. For a
write with strong durability, stale metadata is more dangerous,
because producing to a former leader that has not yet realized it
was deposed can, in the window before it notices, accept a write
that the new leader will not have, and while fencing catches most
of this, the safe move is to refresh metadata before a
high-stakes write if the cache is older than a threshold. The age
tracker gives the client that threshold rather than a fixed
refresh interval, because a fixed interval refreshes needlessly
when the cluster is stable and too rarely when it is churning, and
the right trigger is age-at-use weighted by stakes. It exposes
two thresholds, a lax one for reads and a strict one for durable
writes, so a client refreshes aggressively only when it is about
to do something a stale route could corrupt, and reads keep using
a slightly stale cache without the refresh traffic. The tracker
reports the current age against both thresholds, because a client
deciding whether to refresh needs to know not just that the cache
is old but old relative to what it is about to do, and the same
age is fine for a read and stale for a write in the same instant.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class AgeThresholds:
    read_max_age: int
    write_max_age: int

    def __post_init__(self) -> None:
        if self.write_max_age > self.read_max_age:
            raise Invalid(
                "the write threshold must be at least as strict "
                "as the read one; a durable write cannot tolerate "
                "more staleness than a read"
            )


def refresh_needed(
    thresholds: AgeThresholds,
    age: int,
    for_durable_write: bool,
) -> str:
    limit = (
        thresholds.write_max_age
        if for_durable_write
        else thresholds.read_max_age
    )
    kind = "durable write" if for_durable_write else "read"
    if age <= limit:
        return (
            f"no refresh: age {age} is within the {kind} "
            f"threshold {limit}"
        )
    return (
        f"refresh before this {kind}: age {age} exceeds the "
        f"threshold {limit}, and a stale route could "
        + (
            "accept a write the new leader will not have"
            if for_durable_write
            else "cost one not-leader round trip, self-correcting"
        )
    )


def age_report(thresholds: AgeThresholds, age: int) -> str:
    read_ok = age <= thresholds.read_max_age
    write_ok = age <= thresholds.write_max_age
    return (
        f"age {age}: reads {'ok' if read_ok else 'stale'}, "
        f"durable writes {'ok' if write_ok else 'stale'}; the "
        "same age can be fine for a read and stale for a write"
    )
