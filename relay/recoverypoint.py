"""Recovery point: the marker that says how far the log was known good.

On restart a broker must decide how much of each log to verify,
and verifying everything is safe but slow, prohibitively so for a
large log, while verifying nothing is fast and wrong. The recovery
point is the compromise: it is the offset up to which the log was
known flushed and intact at the last clean checkpoint, so on
restart the broker trusts everything below the recovery point and
verifies only from there to the end, the small unflushed tail that
a crash could have torn. A clean shutdown writes the recovery
point at the log end, so a cleanly-stopped broker verifies almost
nothing and restarts fast. A crash leaves the recovery point at
the last checkpoint before it, so the broker verifies from there
forward, which is bounded by the checkpoint interval, not by the
whole log. The distinction the broker draws on startup is exactly
this: a shutdown that wrote a recovery point at the end was clean
and restarts trusting its log, while a missing or stale recovery
point means a crash and triggers verification of the tail, so the
recovery point doubles as the clean-versus-crash signal. The
checker refuses a recovery point past the log end, because a
recovery point claiming the log was good beyond where it actually
extends would skip verifying real unflushed records, the exact
records a crash endangers, and it reports how much tail must be
verified, because that number is the restart's cost and an
operator waiting on a slow startup deserves to know whether it is
verifying a megabyte or a terabyte.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class RecoveryState:
    recovery_point: int
    log_end: int
    clean_shutdown: bool

    def __post_init__(self) -> None:
        if self.recovery_point > self.log_end:
            raise Invalid(
                "recovery point past the log end would skip "
                "verifying real unflushed records, the exact ones "
                "a crash endangers"
            )


def tail_to_verify(state: RecoveryState) -> int:
    return state.log_end - state.recovery_point


def startup_plan(state: RecoveryState) -> str:
    tail = tail_to_verify(state)
    if state.clean_shutdown and tail == 0:
        return (
            "clean shutdown, recovery point at the end; trust the "
            "whole log and restart fast, verifying nothing"
        )
    if state.clean_shutdown:
        return (
            f"clean shutdown but {tail} record(s) past the "
            "recovery point; verify the tail, a small bounded cost"
        )
    return (
        f"crash detected: recovery point stale, verify {tail} "
        "record(s) of tail; bounded by the checkpoint interval, "
        "not the whole log, and the number an operator waiting on "
        "a slow startup deserves"
    )
