"""Offset reset: where a consumer with no valid position begins, and why.

Two situations leave a consumer without a usable offset: it is
brand new to a partition, or its committed offset fell off the
retained window while it was down. The reset policy decides
where to start, and the choice is a data-correctness decision
disguised as a config value. Earliest replays the whole
retained log, correct for a consumer that must see every event,
catastrophic for one that will reprocess a month of history and
double every side effect. Latest skips to the end, correct for
a live dashboard, silent data loss for a ledger that just
skipped the events it was down for. The resolver refuses to
choose a default, because a broker that silently picks latest
has lost data for every accounting consumer that trusted the
default, and one that silently picks earliest has resent every
email twice; the policy must be stated, and the resolver names
which situation triggered the reset so the log shows whether a
gap was a new consumer or a consumer that fell behind.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid, Lagging

POLICIES = ("earliest", "latest", "error")


@dataclass(frozen=True)
class PartitionBounds:
    first_offset: int
    high_watermark: int


def resolve_reset(
    policy: str,
    committed: int | None,
    bounds: PartitionBounds,
) -> tuple[int, str]:
    if policy not in POLICIES:
        raise Invalid(
            f"unknown reset policy {policy}; one of {POLICIES}"
        )
    if committed is None:
        situation = "new consumer, no committed offset"
    elif committed < bounds.first_offset:
        situation = (
            f"consumer fell behind: committed {committed} is "
            f"below the retained start {bounds.first_offset}"
        )
    else:
        return committed, "committed offset is still valid"
    if policy == "error":
        raise Lagging(
            f"{situation}; the policy is error, because a "
            "broker that silently picks a side loses data for "
            "half its consumers and resends for the other half"
        )
    if policy == "earliest":
        return bounds.first_offset, (
            f"{situation}; reset to earliest "
            f"{bounds.first_offset}, replaying the retained log"
        )
    return bounds.high_watermark, (
        f"{situation}; reset to latest "
        f"{bounds.high_watermark}, skipping what was missed"
    )


@dataclass
class ResetLedger:
    new_consumer_resets: int = 0
    fell_behind_resets: int = 0

    def record(self, situation: str) -> None:
        if situation.startswith("new consumer"):
            self.new_consumer_resets += 1
        elif situation.startswith("consumer fell behind"):
            self.fell_behind_resets += 1

    def report(self) -> str:
        return (
            f"{self.new_consumer_resets} new-consumer reset(s), "
            f"{self.fell_behind_resets} fell-behind reset(s); "
            "the second number is data that aged out before a "
            "consumer read it, and a rising one is a retention "
            "or a consumer problem, never nothing"
        )
