"""Timestamp type: whose clock a record's time reflects, and why it matters.

A topic chooses whether its records carry create-time, the
producer's clock when it made the record, or log-append-time, the
broker's clock when it stored it, and the choice quietly changes
two behaviors most operators never connect to it. Time-based
retention uses the record's timestamp to decide age, so a topic
with create-time retention deletes records based on when the
producer says they were made, which means a producer with a
clock set wrong, or one replaying old data, can make records that
retention deletes immediately because their create-time is
ancient, or keeps forever because it is in the future. Log-append-
time retention uses the broker's own clock, immune to producer
clock skew, at the cost of losing the producer's intended
timestamp for time-based seeks. The stream-time windowing that
aggregates by event time needs create-time, because a window
about when events happened cannot use when the broker filed them,
so a topic feeding event-time analytics must use create-time and
accept the clock-skew exposure, while a topic used only for
retention and audit is safer with log-append-time. The resolver
names the coupling, because the failure mode is silent: a topic
switched from create-time to log-append-time keeps working until
someone runs a time-based query and gets the broker's clock where
they expected the producer's, and a difference that changes query
results without changing any error is the hardest kind to debug.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

CREATE_TIME = "create-time"
LOG_APPEND_TIME = "log-append-time"
TYPES = (CREATE_TIME, LOG_APPEND_TIME)


@dataclass(frozen=True)
class TimestampChoice:
    timestamp_type: str

    def __post_init__(self) -> None:
        if self.timestamp_type not in TYPES:
            raise Invalid(
                f"unknown timestamp type {self.timestamp_type}"
            )


def retention_clock(choice: TimestampChoice) -> str:
    if choice.timestamp_type == CREATE_TIME:
        return (
            "retention ages by the producer's clock; a wrong or "
            "replaying producer can make records delete instantly "
            "or never"
        )
    return (
        "retention ages by the broker's clock, immune to producer "
        "skew, at the cost of the producer's intended timestamp"
    )


def suitable_for_event_time(choice: TimestampChoice) -> str:
    if choice.timestamp_type == CREATE_TIME:
        return (
            "suitable for event-time windowing, which needs when "
            "events happened, not when the broker filed them; "
            "accept the clock-skew exposure"
        )
    return (
        "unsuitable for event-time windowing: the broker's file "
        "time is not the event time, and a window built on it "
        "aggregates the wrong axis"
    )


def switch_warning(
    old: TimestampChoice, new: TimestampChoice
) -> str:
    if old.timestamp_type == new.timestamp_type:
        return "no change"
    return (
        f"switching {old.timestamp_type} -> {new.timestamp_type} "
        "changes time-based query results with no error; a query "
        "gets a different clock than before, the hardest failure "
        "to debug because nothing breaks"
    )
