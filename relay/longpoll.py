"""Long poll: hold the fetch until there is enough, or the wait runs out.

A consumer polling a mostly-idle partition with a plain fetch gets
an empty response most of the time, so it polls again, and the
loop is a busy-wait that burns broker CPU and network on nothing.
The long poll fixes it with two parameters that together turn a
busy-wait into an efficient block. Min-bytes tells the broker not
to respond until at least that many bytes are available, so a
fetch that would return empty instead waits, and one that would
return a trickle instead accumulates into a worthwhile batch.
Max-wait bounds that patience, so a fetch does not wait forever on
a partition that stays idle, returning whatever is there, possibly
nothing, when the wait expires. The interaction is the whole
design: min-bytes trades latency for efficiency, max-wait caps the
latency so the trade has a ceiling, and a consumer sets them
together to say I will wait up to this long to get at least this
much. The broker satisfies the fetch the instant either condition
is met, enough bytes accumulated or the wait elapsed, whichever
comes first, so a burst of data returns immediately without
waiting out the max, and an idle partition returns at the max
without a busy-wait. The resolver refuses a min-bytes larger than
any single response could hold, because a fetch that can never
accumulate its minimum would wait the full max every time and
then return less than asked, the worst of both settings, a
consumer that pays maximum latency for minimum data.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class LongPollRequest:
    min_bytes: int
    max_wait: int
    max_response: int

    def __post_init__(self) -> None:
        if self.min_bytes < 0 or self.max_wait < 1:
            raise Invalid(
                "min-bytes is nonnegative and max-wait positive"
            )
        if self.min_bytes > self.max_response:
            raise Invalid(
                "min-bytes exceeds any single response; the fetch "
                "would wait the full max every time then return "
                "less than asked, maximum latency for minimum data"
            )


def resolve_fetch(
    request: LongPollRequest,
    available_over_time: list[tuple[int, int]],
) -> tuple[int, str]:
    for tick, cumulative in available_over_time:
        if tick > request.max_wait:
            break
        if cumulative >= request.min_bytes:
            return tick, (
                f"returned at tick {tick} with {cumulative} "
                "bytes; the min-bytes condition met before the "
                "max-wait, so a burst does not wait out the timer"
            )
    final = 0
    for tick, cumulative in available_over_time:
        if tick <= request.max_wait:
            final = cumulative
    return request.max_wait, (
        f"returned at max-wait {request.max_wait} with {final} "
        "byte(s); an idle partition returns at the ceiling "
        "without a busy-wait"
    )
