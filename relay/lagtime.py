"""Lag in time: five records behind is seconds here and hours there.

Consumer lag is usually reported as an offset count, the number of
records between the consumer's position and the end of the log, but
that number answers the wrong question during an incident. Five
thousand records behind on a partition taking a million a second is
a few milliseconds of delay, while five thousand behind on a
partition taking one a second is well over an hour, and an operator
deciding whether to page cares about the hour, not the count. Lag
in time answers directly: it is the wall-clock gap between the
timestamp of the record at the log end and the timestamp of the
record the consumer last processed, so it says the consumer is
seeing events as they were some number of seconds ago, regardless
of how many records that spans. The two lags disagree in a way
worth naming: a burst of records with close timestamps inflates
offset lag while barely moving time lag, and a slow trickle with
spread-out timestamps does the opposite, so a consumer with high
offset lag but low time lag is behind on volume but current on
recency, which for many uses is fine. The meter refuses to compute
time lag when the consumer's timestamp is ahead of the log end's,
because that means the clocks disagree or the record timestamps are
not monotonic, and a negative time lag reported as if real would
tell an operator the consumer is ahead of the present. The report
states both lags, because the decision to scale consumers up
depends on which one is growing.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class LagReading:
    end_offset: int
    consumed_offset: int
    end_timestamp: int
    consumed_timestamp: int

    def __post_init__(self) -> None:
        if self.consumed_offset > self.end_offset:
            raise Invalid(
                "the consumer cannot be past the log end"
            )
        if self.consumed_timestamp > self.end_timestamp:
            raise Invalid(
                "the consumed timestamp is ahead of the log end's; "
                "the clocks disagree or timestamps are not "
                "monotonic, and a negative time lag would read as "
                "the consumer being ahead of the present"
            )

    def offset_lag(self) -> int:
        return self.end_offset - self.consumed_offset

    def time_lag(self) -> int:
        return self.end_timestamp - self.consumed_timestamp

    def recency_note(self) -> str:
        offset_lag = self.offset_lag()
        time_lag = self.time_lag()
        if offset_lag > 0 and time_lag == 0:
            return (
                f"{offset_lag} record(s) behind but 0 time lag: "
                "behind on volume, current on recency, which for "
                "many uses is fine"
            )
        return (
            f"{offset_lag} record(s) and {time_lag} time unit(s) "
            "behind; scale on whichever is growing, not the count "
            "alone"
        )
