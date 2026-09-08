"""Backpressure: a slow stage should slow the source, not hide a growing backlog.

A processing pipeline is a chain of stages, each consuming from the
one before and producing to the one after, and its throughput is
bounded by its slowest stage, the bottleneck. What happens to the
faster stages upstream of the bottleneck is the design question.
The right behavior is backpressure: the bottleneck's input buffer
fills, which blocks the stage feeding it from producing more, which
fills that stage's buffer and blocks the one before, propagating the
slowdown all the way back to the source, so the source produces only
as fast as the bottleneck consumes and the whole pipeline runs at
the bottleneck's rate with bounded memory. The wrong behavior is an
unbounded buffer somewhere: a stage that accepts everything the
upstream sends, buffering the backlog instead of blocking, hides
the backpressure and lets the backlog grow until it exhausts memory,
turning a throughput mismatch into an out-of-memory crash, the
bufferbloat failure. So bounded buffers everywhere are what make
backpressure work, because a bounded buffer that fills is what
transmits the slowdown upstream. The model takes each stage's
processing rate and buffer bound, finds the bottleneck as the
slowest stage, and determines whether the pipeline reaches a stable
bounded state (every buffer bounded, source throttled) or an
unstable one (an unbounded buffer that will grow). It refuses a
stage with a non-positive rate, which processes nothing and stalls
the pipeline, and reports the bottleneck stage and the rate the
whole pipeline is limited to, because speeding up any stage but the
bottleneck buys nothing, and knowing which stage is the bottleneck
is the difference between fixing the pipeline and tuning the wrong
part of it."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class Stage:
    name: str
    rate: float
    bounded_buffer: bool = True


@dataclass
class Pipeline:
    stages: list[Stage] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.stages:
            raise Invalid("a pipeline needs at least one stage")
        if any(s.rate <= 0 for s in self.stages):
            raise Invalid("a stage rate must be positive; a zero rate stalls the pipeline")

    def bottleneck(self) -> Stage:
        return min(self.stages, key=lambda s: s.rate)

    def throughput(self) -> float:
        return self.bottleneck().rate

    def is_stable(self) -> bool:
        # stable iff every stage has a bounded buffer, so a full buffer
        # transmits backpressure upstream rather than absorbing a backlog
        return all(s.bounded_buffer for s in self.stages)

    def report(self) -> str:
        b = self.bottleneck()
        if not self.is_stable():
            unbounded = [s.name for s in self.stages if not s.bounded_buffer]
            return (
                f"UNSTABLE: {unbounded} have unbounded buffers absorbing the "
                "backlog instead of transmitting backpressure; it grows to OOM, "
                "the bufferbloat failure"
            )
        return (
            f"stable at the bottleneck '{b.name}' rate {b.rate}; the source is "
            "throttled to it, so speeding up any other stage buys nothing"
        )
